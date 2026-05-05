import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowRight } from "lucide-react";
import { CustomLink } from "@/customization/components/custom-link";
import IconComponent from "../../../../components/common/genericIconComponent";
import type { SingleAlertComponentType } from "../../../../types/alerts";

export default function SingleAlert({
  dropItem,
  removeAlert,
  navigateTo,
  onClosePanel,
}: SingleAlertComponentType): JSX.Element {
  const [_show, setShow] = useState(true);
  const navigate = useNavigate();
  const type = dropItem.type;

  const dismiss = () => {
    setShow(false);
    setTimeout(() => removeAlert(dropItem.id), 500);
  };

  const handleCardClick = () => {
    if (!navigateTo) return;
    onClosePanel?.();
    navigate(navigateTo);
  };

  const clickableClass = navigateTo ? " cursor-pointer hover:opacity-90 transition-opacity" : "";

  return type === "error" ? (
    <div
      className={`mx-2 mb-2 flex rounded-md bg-error-background p-3${clickableClass}`}
      key={dropItem.id}
      onClick={handleCardClick}
    >
      <div className="flex-shrink-0">
        <IconComponent name="XCircle" className="h-5 w-5 text-status-red" />
      </div>
      <div className="ml-3 flex-1">
        <h3 className={`text-sm font-medium text-error-foreground word-break-break-word${navigateTo ? " underline underline-offset-2" : ""}`}>
          {dropItem.title}
        </h3>
        {dropItem.list ? (
          <div className="mt-2 text-sm text-error-foreground">
            <ul className="list-disc space-y-1 pl-5 align-top">
              {dropItem.list.map((item, idx) => (
                <li className="word-break-break-word" key={idx}>
                  <Markdown
                    linkTarget="_blank"
                    remarkPlugins={[remarkGfm]}
                    className="align-text-top"
                    components={{
                      a: ({ node, ...props }) => (
                        <a
                          href={props.href}
                          target="_blank"
                          className="underline"
                          rel="noopener noreferrer"
                        >
                          {props.children}
                        </a>
                      ),
                      p({ node, ...props }) {
                        return (
                          <span className="inline-block w-fit max-w-full align-text-top">
                            {props.children}
                          </span>
                        );
                      },
                    }}
                  >
                    {Array.isArray(item) ? item.join("\n") : item}
                  </Markdown>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <div className="ml-auto flex items-start gap-1 pl-3" onClick={(e) => e.stopPropagation()}>
        {navigateTo && (
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-error-foreground opacity-60" />
        )}
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={dismiss}
            className="inline-flex rounded-md p-1.5 text-status-red"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent name="X" className="h-4 w-4 text-error-foreground" />
          </button>
        </div>
      </div>
    </div>
  ) : type === "notice" ? (
    <div
      className={`mx-2 mb-2 flex rounded-md bg-info-background p-3${clickableClass}`}
      key={dropItem.id}
      onClick={handleCardClick}
    >
      <div className="flex-shrink-0">
        <IconComponent name="Info" className="h-5 w-5 text-status-blue" />
      </div>
      <div className="ml-3 flex-1 md:flex md:justify-between">
        <p className={`text-sm font-medium text-info-foreground${navigateTo ? " underline underline-offset-2" : ""}`}>
          {dropItem.title}
        </p>
        {dropItem.link && (
          <p className="mt-3 text-sm md:ml-6 md:mt-0" onClick={(e) => e.stopPropagation()}>
            <CustomLink
              to={dropItem.link}
              className="whitespace-nowrap font-medium text-info-foreground hover:text-accent-foreground"
            >
              Details
            </CustomLink>
          </p>
        )}
      </div>
      <div className="ml-auto flex items-start gap-1 pl-3" onClick={(e) => e.stopPropagation()}>
        {navigateTo && (
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-info-foreground opacity-60" />
        )}
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={dismiss}
            className="inline-flex rounded-md p-1.5 text-info-foreground"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent name="X" className="h-4 w-4 text-info-foreground" />
          </button>
        </div>
      </div>
    </div>
  ) : (
    <div
      className={`mx-2 mb-2 flex rounded-md bg-success-background p-3${clickableClass}`}
      key={dropItem.id}
      onClick={handleCardClick}
    >
      <div className="flex-shrink-0">
        <IconComponent
          name="CheckCircle2"
          className="h-5 w-5 text-status-green"
        />
      </div>
      <div className="ml-3 flex-1">
        <p className={`text-sm font-medium text-success-foreground${navigateTo ? " underline underline-offset-2" : ""}`}>
          {dropItem.title}
        </p>
      </div>
      <div className="ml-auto flex items-start gap-1 pl-3" onClick={(e) => e.stopPropagation()}>
        {navigateTo && (
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-success-foreground opacity-60" />
        )}
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={dismiss}
            className="inline-flex rounded-md p-1.5 text-status-green"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent
              name="X"
              className="h-4 w-4 text-success-foreground"
            />
          </button>
        </div>
      </div>
    </div>
  );
}
