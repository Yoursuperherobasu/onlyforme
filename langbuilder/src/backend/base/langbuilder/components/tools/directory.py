from loguru import logger

from langbuilder.base.data.utils import (
    TEXT_FILE_TYPES,
    parallel_load_data,
    parse_text_file_to_data,
    retrieve_file_paths,
)
from langbuilder.custom.custom_component.component import Node
from langbuilder.io import BoolInput, IntInput, MessageTextInput, MultiselectInput
from langbuilder.schema.data import Data
from langbuilder.schema.dataframe import DataFrame
from langbuilder.template.field.base import Output


class DirectoryComponent(Node):
    display_name = "Directory"
    description = "Recursively load files from a directory."
    documentation: str = "https://docs.langbuilder.org/components-data#directory"
    icon = "folder"
    name = "Directory"

    inputs = [
        MessageTextInput(
            name="path",
            display_name="Path",
            info="Path to the directory to load files from. Defaults to current directory ('.')",
            value=".",
            tool_mode=True,
        ),
        MultiselectInput(
            name="types",
            display_name="File Types",
            info="File types to load. Select one or more types or leave empty to load all supported types.",
            options=TEXT_FILE_TYPES,
            value=[],
        ),
        IntInput(
            name="depth",
            display_name="Depth",
            info="Depth to search for files.",
            value=0,
        ),
        IntInput(
            name="max_concurrency",
            display_name="Max Concurrency",
            advanced=True,
            info="Maximum concurrency for loading files.",
            value=2,
        ),
        BoolInput(
            name="load_hidden",
            display_name="Load Hidden",
            advanced=True,
            info="If true, hidden files will be loaded.",
        ),
        BoolInput(
            name="recursive",
            display_name="Recursive",
            advanced=True,
            info="If true, the search will be recursive.",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
        BoolInput(
            name="use_multithreading",
            display_name="Use Multithreading",
            advanced=True,
            info="If true, multithreading will be used.",
        ),
    ]

    outputs = [
        Output(display_name="Loaded Files", name="dataframe", method="as_dataframe"),
    ]

    def load_directory(self) -> list[Data]:
        path = self.path
        types = self.types
        depth = self.depth
        max_concurrency = self.max_concurrency
        load_hidden = self.load_hidden
        recursive = self.recursive
        silent_errors = self.silent_errors
        use_multithreading = self.use_multithreading

        resolved_path = self.resolve_path(path)
        
        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: input path = {path}")
        print(f"📂 DIRECTORY DEBUG: resolved_path = {resolved_path}")
        print(f"📂 DIRECTORY DEBUG: types = {types}")
        logger.info(f"📂 DIRECTORY DEBUG: input path = {path}")
        logger.info(f"📂 DIRECTORY DEBUG: resolved_path = {resolved_path}")
        logger.info(f"📂 DIRECTORY DEBUG: types = {types}")

        # If no types are specified, use all supported types
        if not types:
            types = TEXT_FILE_TYPES

        # Check if all specified types are valid
        invalid_types = [t for t in types if t not in TEXT_FILE_TYPES]
        if invalid_types:
            msg = f"Invalid file types specified: {invalid_types}. Valid types are: {TEXT_FILE_TYPES}"
            raise ValueError(msg)

        valid_types = types

        file_paths = retrieve_file_paths(
            resolved_path, load_hidden=load_hidden, recursive=recursive, depth=depth, types=valid_types
        )
        
        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: file_paths found = {file_paths}")
        print(f"📂 DIRECTORY DEBUG: file_paths count = {len(file_paths)}")
        logger.info(f"📂 DIRECTORY DEBUG: file_paths found = {file_paths}")
        logger.info(f"📂 DIRECTORY DEBUG: file_paths count = {len(file_paths)}")

        loaded_data = []
        if use_multithreading:
            loaded_data = parallel_load_data(file_paths, silent_errors=silent_errors, max_concurrency=max_concurrency)
        else:
            loaded_data = [parse_text_file_to_data(file_path, silent_errors=silent_errors) for file_path in file_paths]

        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: loaded_data count = {len(loaded_data)}")
        logger.info(f"📂 DIRECTORY DEBUG: loaded_data count = {len(loaded_data)}")
        for i, data in enumerate(loaded_data):
            if data is not None:
                print(f"📂 DIRECTORY DEBUG: loaded_data[{i}] type = {type(data)}")
                logger.info(f"📂 DIRECTORY DEBUG: loaded_data[{i}] type = {type(data)}")
                if hasattr(data, 'data'):
                    print(f"📂 DIRECTORY DEBUG: loaded_data[{i}].data = {data.data}")
                    logger.info(f"📂 DIRECTORY DEBUG: loaded_data[{i}].data = {data.data}")
                if hasattr(data, 'file_path'):
                    print(f"📂 DIRECTORY DEBUG: loaded_data[{i}].file_path = {data.file_path}")
                    logger.info(f"📂 DIRECTORY DEBUG: loaded_data[{i}].file_path = {data.file_path}")

        valid_data = [x for x in loaded_data if x is not None and isinstance(x, Data)]
        
        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: valid_data count = {len(valid_data)}")
        logger.info(f"📂 DIRECTORY DEBUG: valid_data count = {len(valid_data)}")
        for i, data in enumerate(valid_data):
            print(f"📂 DIRECTORY DEBUG: valid_data[{i}] = {data}")
            logger.info(f"📂 DIRECTORY DEBUG: valid_data[{i}] = {data}")
            if hasattr(data, 'data'):
                print(f"📂 DIRECTORY DEBUG: valid_data[{i}].data keys = {data.data.keys() if isinstance(data.data, dict) else 'not a dict'}")
                print(f"📂 DIRECTORY DEBUG: valid_data[{i}].data = {data.data}")
                logger.info(f"📂 DIRECTORY DEBUG: valid_data[{i}].data keys = {data.data.keys() if isinstance(data.data, dict) else 'not a dict'}")
                logger.info(f"📂 DIRECTORY DEBUG: valid_data[{i}].data = {data.data}")
        
        self.status = valid_data
        return valid_data

    def as_dataframe(self) -> DataFrame:
        data_list = self.load_directory()
        
        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: as_dataframe called with {len(data_list)} items")
        logger.info(f"📂 DIRECTORY DEBUG: as_dataframe called with {len(data_list)} items")
        
        df = DataFrame(data_list)
        
        # DEBUG LOGGING - using print for guaranteed visibility
        print(f"📂 DIRECTORY DEBUG: DataFrame created")
        print(f"📂 DIRECTORY DEBUG: DataFrame type = {type(df)}")
        print(f"📂 DIRECTORY DEBUG: DataFrame columns = {list(df.columns) if hasattr(df, 'columns') else 'no columns'}")
        print(f"📂 DIRECTORY DEBUG: DataFrame shape = {df.shape if hasattr(df, 'shape') else 'no shape'}")
        print(f"📂 DIRECTORY DEBUG: DataFrame head:\n{df.head() if hasattr(df, 'head') else df}")
        logger.info(f"📂 DIRECTORY DEBUG: DataFrame created")
        logger.info(f"📂 DIRECTORY DEBUG: DataFrame type = {type(df)}")
        logger.info(f"📂 DIRECTORY DEBUG: DataFrame columns = {list(df.columns) if hasattr(df, 'columns') else 'no columns'}")
        logger.info(f"📂 DIRECTORY DEBUG: DataFrame shape = {df.shape if hasattr(df, 'shape') else 'no shape'}")
        logger.info(f"📂 DIRECTORY DEBUG: DataFrame head:\n{df.head() if hasattr(df, 'head') else df}")
        
        if 'file_path' in df.columns:
            print(f"📂 DIRECTORY DEBUG: file_path column values = {df['file_path'].tolist()}")
            logger.info(f"📂 DIRECTORY DEBUG: file_path column values = {df['file_path'].tolist()}")
        
        return df
