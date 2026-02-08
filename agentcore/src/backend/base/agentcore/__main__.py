import asyncio
import inspect
import os
import platform
import signal
import socket
import sys
import time
import warnings
from contextlib import suppress
from ipaddress import ip_address
from pathlib import Path

import click
import httpx
import typer
from dotenv import load_dotenv
from httpx import HTTPError
from loguru import logger
from multiprocess import cpu_count
from multiprocess.context import Process
from packaging import version as pkg_version
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import select

from agentcore.initial_setup.setup import get_or_create_default_folder
from agentcore.logging.logger import configure, logger
from agentcore.main import setup_app
from agentcore.services.database.utils import session_getter
from agentcore.services.deps import get_db_service, get_settings_service, session_scope
from agentcore.services.utils import initialize_services
from agentcore.utils.version import fetch_latest_version, get_version_info
from agentcore.utils.version import is_pre_release as agentcore_is_pre_release

# Initialize console with Windows-safe settings
console = Console(legacy_windows=True, emoji=False) if platform.system() == "Windows" else Console()

app = typer.Typer(no_args_is_help=True)


class ProcessManager:
    """Manages the lifecycle of the backend process."""

    def __init__(self):
        self.webapp_process = None
        self.shutdown_in_progress = False
        if platform.system() == "Windows":
            self._farewell_emoji = ":)"  # ASCII smiley
        else:
            self._farewell_emoji = "Goodbye"  # Unicode not needed

    # params are required for signal handlers, even if they are not used
    def handle_sigterm(self, _signum: int, _frame) -> None:
        """Handle SIGTERM signal gracefully."""
        if self.shutdown_in_progress:
            return  # Already shutting down, ignore
        self.shutdown_in_progress = True
        self.shutdown()

    # params are required for signal handlers, even if they are not used
    def handle_sigint(self, _signum: int, _frame) -> None:
        """Handle SIGINT signal gracefully."""
        if self.shutdown_in_progress:
            return  # Already shutting down, ignore
        self.shutdown_in_progress = True
        self.shutdown()

    def shutdown(self):
        """Gracefully shutdown the webapp process."""
        if self.webapp_process and self.webapp_process.is_alive():
            # Just terminate the process - the actual shutdown progress is handled
            # by the FastAPI lifespan context in main.py
            self.webapp_process.terminate()
            # The long wait allows the process to finish setup, preventing it from
            # getting in a state where background tasks continue to do work after termination
            # is sent.
            self.webapp_process.join(timeout=30)
            if self.webapp_process.is_alive():
                logger.warning("Process didn't terminate gracefully, killing it.")
                self.webapp_process.kill()
                self.webapp_process.join()
            self.print_farewell_message()

        sys.exit(0)

    def print_farewell_message(self) -> None:
        """Print a nice farewell message after shutdown is complete."""
        # Clear any progress indicator output that might be on the current line
        sys.stdout.write("\r")  # Move cursor to beginning of line
        sys.stdout.write(" " * 80)  # Clear the line with spaces
        sys.stdout.write("\r")  # Move cursor back to beginning

        click.echo()
        farewell = click.style(f"{self._farewell_emoji} See you next time!", fg="bright_blue", bold=True)
        click.echo(farewell)


# Create a single instance of ProcessManager
process_manager = ProcessManager()

# Update signal handlers to use the instance methods
signal.signal(signal.SIGTERM, process_manager.handle_sigterm)
signal.signal(signal.SIGINT, process_manager.handle_sigint)


def get_number_of_workers(workers=None):
    if workers == -1 or workers is None:
        workers = (cpu_count() * 2) + 1
    logger.debug(f"Number of workers: {workers}")
    return workers


def display_results(results) -> None:
    """Display the results of the migration."""
    for table_results in results:
        table = Table(title=f"Migration {table_results.table_name}")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Status")

        for result in table_results.results:
            status = "Success" if result.success else "Failure"
            color = "green" if result.success else "red"
            table.add_row(result.name, result.type, f"[{color}]{status}[/{color}]")

        console.print(table)
        console.print()  # Print a new line


def set_var_for_macos_issue() -> None:
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    # we need to set this var is we are running on MacOS
    # otherwise we get an error when running gunicorn

    if platform.system() == "Darwin":
        import os

        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        os.environ["no_proxy"] = "*"  # to avoid error with gunicorn
        logger.debug("Set OBJC_DISABLE_INITIALIZE_FORK_SAFETY to YES to avoid error")


def wait_for_server_ready(host, port, protocol) -> None:
    """Wait for the server to become ready by polling the health endpoint."""
    # Use localhost for health check when host is 0.0.0.0 (bind to all interfaces)
    health_check_host = "localhost" if host == "0.0.0.0" else host  # noqa: S104

    status_code = 0
    while status_code != httpx.codes.OK:
        try:
            status_code = httpx.get(
                f"{protocol}://{health_check_host}:{port}/health",
                verify=health_check_host not in ("127.0.0.1", "localhost"),
            ).status_code
        except HTTPError:
            time.sleep(1)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error while waiting for the server to become ready.")
            time.sleep(1)


@app.command()
def run(
    *,
    host: str | None = typer.Option(None, help="Host to bind the server to.", show_default=False),
    workers: int | None = typer.Option(None, help="Number of worker processes.", show_default=False),
    worker_timeout: int | None = typer.Option(None, help="Worker timeout in seconds.", show_default=False),
    port: int | None = typer.Option(None, help="Port to listen on.", show_default=False),
    components_path: Path | None = typer.Option(
        Path(__file__).parent / "components",
        help="Path to the directory containing custom components.",
        show_default=False,
    ),
    # .env file param
    env_file: Path | None = typer.Option(
        None,
        help="Path to the .env file containing environment variables.",
        show_default=False,
    ),
    log_level: str | None = typer.Option(
        None,
        help="Logging level. One of: [debug, info, warning, error, critical]. Defaults to info.",
        show_default=False,
    ),
    log_file: Path | None = typer.Option(None, help="Path to the log file.", show_default=False),
    log_rotation: str | None = typer.Option(None, help="Log rotation(Time/Size).", show_default=False),
    cache: str | None = typer.Option(  # noqa: ARG001
        None,
        help="Type of cache to use. (InMemoryCache, SQLiteCache)",
        show_default=False,
    ),
    dev: bool | None = typer.Option(None, help="Run in development mode (may contain bugs)", show_default=False),  # noqa: ARG001
    frontend_path: str | None = typer.Option(
        None,
        help="Path to the frontend directory containing build files. This is for development purposes only.",
        show_default=False,
    ),
    open_browser: bool | None = typer.Option(
        None,
        help="Open the browser after starting the server.",
        show_default=False,
    ),
    remove_api_keys: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Remove API keys from the projects saved in the database.",
        show_default=False,
    ),
    backend_only: bool | None = typer.Option(
        None,
        help="Run only the backend server without the frontend.",
        show_default=False,
    ),
    store: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Enables the store features.",
        show_default=False,
    ),
    auto_saving: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines if the auto save is enabled.",
        show_default=False,
    ),
    auto_saving_interval: int | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the debounce time for the auto save.",
        show_default=False,
    ),
    health_check_max_retries: bool | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the number of retries for the health check.",
        show_default=False,
    ),
    max_file_size_upload: int | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the maximum file size for the upload in MB.",
        show_default=False,
    ),
    webhook_polling_interval: int | None = typer.Option(  # noqa: ARG001
        None,
        help="Defines the polling interval for the webhook.",
        show_default=False,
    ),
    ssl_cert_file_path: str | None = typer.Option(
        None, help="Defines the SSL certificate file path.", show_default=False
    ),
    ssl_key_file_path: str | None = typer.Option(None, help="Defines the SSL key file path.", show_default=False),
) -> None:
    """Run Agentcore."""
    if env_file:
        load_dotenv(env_file, override=True)

    # Set default log level if not provided
    log_level_str = "info" if log_level is None else log_level.lower()

    # Must set as env var for child process to pick up
    env_log_level = os.environ.get("AGENTCORE_LOG_LEVEL")
    if env_log_level is None:
        os.environ["AGENTCORE_LOG_LEVEL"] = log_level_str
    else:
        os.environ["AGENTCORE_LOG_LEVEL"] = env_log_level.lower()

    configure(log_level=log_level, log_file=log_file, log_rotation=log_rotation)

    # Initializing Agentcore
    logger.debug(f"Loading config from file: '{env_file}'" if env_file else "No env_file provided.")
    set_var_for_macos_issue()
    settings_service = get_settings_service()

    # Checking Environment
    for key, value in os.environ.items():
        new_key = key.replace("AGENTCORE_", "")
        if hasattr(settings_service.auth_settings, new_key):
            setattr(settings_service.auth_settings, new_key, value)

    frame = inspect.currentframe()
    valid_args: list = []
    values: dict = {}
    if frame is not None:
        arguments, _, _, values = inspect.getargvalues(frame)
        valid_args = [arg for arg in arguments if values[arg] is not None]

    for arg in valid_args:
        if arg == "components_path":
            settings_service.settings.update_settings(components_path=components_path)
        elif hasattr(settings_service.settings, arg):
            settings_service.set(arg, values[arg])
        elif hasattr(settings_service.auth_settings, arg):
            settings_service.auth_settings.set(arg, values[arg])
        logger.debug(f"Loading config from cli parameter '{arg}': '{values[arg]}'")

    # Get final values from settings
    host = settings_service.settings.host
    port = settings_service.settings.port
    workers = settings_service.settings.workers
    worker_timeout = settings_service.settings.worker_timeout
    log_level = settings_service.settings.log_level
    frontend_path = settings_service.settings.frontend_path
    backend_only = settings_service.settings.backend_only
    ssl_cert_file_path = (
        settings_service.settings.ssl_cert_file if ssl_cert_file_path is None else ssl_cert_file_path
    )
    ssl_key_file_path = settings_service.settings.ssl_key_file if ssl_key_file_path is None else ssl_key_file_path

    # create path object if frontend_path is provided
    static_files_dir: Path | None = Path(frontend_path) if frontend_path else None

    # Starting Core Services
    app = setup_app(static_files_dir=static_files_dir, backend_only=backend_only)

    # Connecting Database (this happens inside setup_app via dependencies)
    # check if port is being used
    if is_port_in_use(port, host):
        port = get_free_port(port)

    protocol = "https" if ssl_cert_file_path and ssl_key_file_path else "http"

    # Launching Agentcore
    if platform.system() == "Windows":
        import uvicorn

        print_banner(host, port, protocol)

        # Blocking call
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level,
            reload=False,
            workers=get_number_of_workers(workers),
            loop="asyncio",
        )
    else:
        # Use Gunicorn with AgentcoreUvicornWorker for non-Windows systems
        from agentcore.server import AgentcoreApplication

        options = {
            "bind": f"{host}:{port}",
            "workers": get_number_of_workers(workers),
            "timeout": worker_timeout,
            "certfile": ssl_cert_file_path,
            "keyfile": ssl_key_file_path,
            "log_level": log_level.lower(),
        }
        server = AgentcoreApplication(app, options)

        # Start the webapp process
        process_manager.webapp_process = Process(target=server.run)
        process_manager.webapp_process.start()

        wait_for_server_ready(host, port, protocol)

        print_banner(host, port, protocol)

        # Handle browser opening
        if open_browser and not backend_only:
            click.launch(f"{protocol}://{host}:{port}")

        try:
            process_manager.webapp_process.join()
        except KeyboardInterrupt:
            # SIGINT should be handled by the signal handler, but leaving here for safety
            logger.warning("KeyboardInterrupt caught in main thread")
        finally:
            process_manager.shutdown()


def is_port_in_use(port, host="localhost"):
    """Check if a port is in use.

    Args:
        port (int): The port number to check.
        host (str): The host to check the port on. Defaults to 'localhost'.

    Returns:
        bool: True if the port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def get_free_port(port):
    """Given a used port, find a free port.

    Args:
        port (int): The port number to check.

    Returns:
        int: A free port number.
    """
    while is_port_in_use(port):
        port += 1
    return port


def is_loopback_address(host: str) -> bool:
    """Check if a host is a loopback address (localhost, 127.0.0.1, ::1, etc.).

    Args:
        host: The host address to check

    Returns:
        bool: True if the host is a loopback address, False otherwise
    """
    # Check if it's exactly "localhost"
    if host == "localhost":
        return True

    # Check if it's exactly "0.0.0.0" (which binds to all interfaces)
    if host == "0.0.0.0":  # noqa: S104
        return True

    try:
        # Convert string to IP address object
        ip = ip_address(host)
        # Check if it's a loopback address (127.0.0.0/8 for IPv4, ::1 for IPv6)
        return bool(ip.is_loopback)
    except ValueError:
        # If the IP address is invalid, default to False
        return False


def can_connect(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            family, socktype, proto, _, sa = res
            with socket.socket(family, socktype, proto) as s:
                s.settimeout(timeout)
                if s.connect_ex(sa) == 0:
                    return True
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to connect to %s:%s", host, port, exc_info=e)
    return False


def get_best_access_host(host: str, port: int) -> str:
    """Get the best host to use for accessing the server.

    For loopback addresses, we prefer 'localhost' over IP addresses like '127.0.0.1'
    because 'localhost' is more universally supported across different operating systems
    and network configurations.

    Args:
        host: The original host address
        port: The port number

    Returns:
        str: The best host address to use for access
    """
    if not is_loopback_address(host):
        return host

    if host != "localhost" and can_connect("localhost", port):
        return "localhost"
    if can_connect(host, port):
        return host
    return "localhost"


def get_letter_from_version(version: str) -> str | None:
    """Get the letter from a pre-release version."""
    if "a" in version:
        return "a"
    if "b" in version:
        return "b"
    if "rc" in version:
        return "rc"
    return None


def build_version_notice(current_version: str, package_name: str) -> str:
    """Build a version notice message if a newer version is available.

    This function checks if there is a newer version of the package available on PyPI
    and returns an appropriate notice message.

    Args:
        current_version (str): The currently installed version of the package
        package_name (str): The name of the package to check

    Returns:
        str: A notice message if a newer version is available, empty string otherwise.
            The message will indicate if the newer version is a pre-release.

    Example:
        >>> build_version_notice("1.0.0", "agentcore")
        'A new version of agentcore is available: 1.1.0'
    """
    with suppress(httpx.ConnectError):
        latest_version = fetch_latest_version(package_name, include_prerelease=agentcore_is_pre_release(current_version))
        if latest_version and pkg_version.parse(current_version) < pkg_version.parse(latest_version):
            release_type = "pre-release" if agentcore_is_pre_release(latest_version) else "version"
            return f"A new {release_type} of {package_name} is available: {latest_version}"
    return ""


def generate_pip_command(package_names, is_pre_release) -> str:
    """Generate the pip install command based on the packages and whether it's a pre-release."""
    base_command = "pip install"
    if is_pre_release:
        return f"{base_command} {' '.join(package_names)} -U --pre"
    return f"{base_command} {' '.join(package_names)} -U"


def stylize_text(text: str, to_style: str, *, is_prerelease: bool) -> str:
    color = "#42a7f5" if is_prerelease else "#6e42f5"
    # return "".join(f"[{color}]{char}[/]" for char in text)
    styled_text = f"[{color}]{to_style}[/]"
    return text.replace(to_style, styled_text)


def print_banner(host: str, port: int, protocol: str) -> None:
    notices = []
    package_names = []  # Track package names for pip install instructions
    is_pre_release = False  # Track if any package is a pre-release
    package_name = ""

    # Use agentcore.utils.version to get the version info
    version_info = get_version_info()
    agentcore_version = version_info["version"]
    package_name = version_info["package"]
    is_pre_release |= agentcore_is_pre_release(agentcore_version)  # Update pre-release status

    notice = build_version_notice(agentcore_version, package_name)

    notice = stylize_text(notice, package_name, is_prerelease=is_pre_release)
    if notice:
        notices.append(notice)
    package_names.append(package_name)

    # Generate pip command based on the collected data
    pip_command = generate_pip_command(package_names, is_pre_release)

    # Add pip install command to notices if any package needs an update
    if notices:
        notices.append(f"Run '{pip_command}' to update.")

    [f"[bold]{notice}[/bold]" for notice in notices if notice]
    styled_package_name = stylize_text(
        package_name, package_name, is_prerelease=any("pre-release" in notice for notice in notices)
    )

    title = f"[bold]Welcome to {styled_package_name}[/bold]\n"

    # Use Windows-safe characters to prevent encoding issues
    import platform

    if platform.system() == "Windows":
        arrow = "->"
        status_icon = "[OK]"
    else:
        arrow = "→"
        status_icon = "[OK]"

    info_text = "AgentCore - AI Agent Builder"
    telemetry_text = (
        (
            "We collect anonymous usage data to improve Agentcore.\n"
            "To opt out, set: [bold]DO_NOT_TRACK=true[/bold] in your environment."
        )
        if os.getenv("DO_NOT_TRACK", os.getenv("AGENTCORE_DO_NOT_TRACK", "False")).lower() != "true"
        else (
            "We are [bold]not[/bold] collecting anonymous usage data to improve Agentcore.\n"
            "To contribute, set: [bold]DO_NOT_TRACK=false[/bold] in your environment."
        )
    )
    access_host = get_best_access_host(host, port)
    access_link = f"[bold]{status_icon} Open Agentcore {arrow}[/bold] [link={protocol}://{access_host}:{port}]{protocol}://{access_host}:{port}[/link]"

    message = f"{title}\n{info_text}\n\n{telemetry_text}\n\n{access_link}"

    # Handle Unicode encoding errors on Windows
    try:
        console.print()  # Add line break before banner
        console.print(Panel.fit(message, border_style="#7528FC", padding=(1, 2)))
    except UnicodeEncodeError:
        # Fallback to a simpler banner without emojis for Windows systems with encoding issues
        fallback_message = (
            f"Welcome to {package_name}\n\n"
            f"{telemetry_text}\n\n"
            f"[OK] Open Agentcore -> {protocol}://{access_host}:{port}"
        )
        try:
            console.print()  # Add line break before fallback banner
            console.print(Panel.fit(fallback_message, border_style="#7528FC", padding=(1, 2)))
        except UnicodeEncodeError:
            # Last resort: use logger instead of print
            logger.info(f"Welcome to {package_name}")
            logger.info(f"Open Agentcore: {protocol}://{access_host}:{port}")


@app.command()
def superuser(
    username: str = typer.Option(..., prompt=True, help="Username for the superuser."),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for the superuser."),
    log_level: str = typer.Option("error", help="Logging level.", envvar="AGENTCORE_LOG_LEVEL"),
) -> None:
    """Create a superuser."""
    configure(log_level=log_level)
    db_service = get_db_service()

    async def _create_superuser():
        await initialize_services()
        async with session_getter(db_service) as session:
            from agentcore.services.auth.utils import create_super_user

            if await create_super_user(db=session, username=username, password=password):
                # Verify that the superuser was created
                from agentcore.services.database.models.user.model import User

                stmt = select(User).where(User.username == username)
                user: User = (await session.exec(stmt)).first()
                if user is None or not user.is_superuser:
                    typer.echo("Superuser creation failed.")
                    return
                # Now create the first folder for the user
                result = await get_or_create_default_folder(session, user.id)
                if result:
                    typer.echo("Default folder created successfully.")
                else:
                    msg = "Could not create default folder."
                    raise RuntimeError(msg)
                typer.echo("Superuser created successfully.")

            else:
                typer.echo("Superuser creation failed.")

    asyncio.run(_create_superuser())


# command to copy the agentcore database from the cache to the current directory
# because now the database is stored per installation
@app.command()
def copy_db() -> None:
    """Copy the database files to the current directory.

    This function copies the 'agentcore.db' and 'agentcore-pre.db' files from the cache directory to the current
    directory.
    If the files exist in the cache directory, they will be copied to the same directory as this script (__main__.py).

    Returns:
        None
    """
    import shutil

    from platformdirs import user_cache_dir

    cache_dir = Path(user_cache_dir("agentcore"))
    db_path = cache_dir / "agentcore.db"
    pre_db_path = cache_dir / "agentcore-pre.db"
    # It should be copied to the current directory
    # this file is __main__.py and it should be in the same directory as the database
    destination_folder = Path(__file__).parent
    if db_path.exists():
        shutil.copy(db_path, destination_folder)
        typer.echo(f"Database copied to {destination_folder}")
    else:
        typer.echo("Database not found in the cache directory.")
    if pre_db_path.exists():
        shutil.copy(pre_db_path, destination_folder)
        typer.echo(f"Pre-release database copied to {destination_folder}")
    else:
        typer.echo("Pre-release database not found in the cache directory.")


async def _migration(*, test: bool, fix: bool) -> None:
    await initialize_services(fix_migration=fix)
    db_service = get_db_service()
    if not test:
        await db_service.run_migrations()
    results = await db_service.run_migrations_test()
    display_results(results)


@app.command()
def migration(
    test: bool = typer.Option(default=True, help="Run migrations in test mode."),  # noqa: FBT001
    fix: bool = typer.Option(  # noqa: FBT001
        default=False,
        help="Fix migrations. This is a destructive operation, and should only be used if you know what you are doing.",
    ),
) -> None:
    """Run or test migrations."""
    if fix and not typer.confirm(
        "This will delete all data necessary to fix migrations. Are you sure you want to continue?"
    ):
        raise typer.Abort

    asyncio.run(_migration(test=test, fix=fix))


def show_version(*, value: bool):
    if value:
        default = "DEV"
        raw_info = get_version_info()
        version = raw_info.get("version", default) if raw_info else default
        typer.echo(f"agentcore {version}")
        raise typer.Exit


@app.callback()
def version_option(
    *,
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=show_version,
        is_eager=True,
        help="Show the version and exit.",
    ),
):
    pass


def main() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(e)
        raise typer.Exit(1) from e
