import {
  PDFCheckAgent,
  PDFLoadErrorTitle,
} from "../../../../constants/constants";
import IconComponent from "../../../common/genericIconComponent";

export default function ErrorComponent(): JSX.Element {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="chat-alert-box">
        <span className="flex gap-2">
          <IconComponent name="FileX2" />
          <span className="sensei-chat-span">{PDFLoadErrorTitle}</span>
        </span>
        <br />
        <div className="sensei-chat-desc">
          <span className="sensei-chat-desc-span">{PDFCheckAgent} </span>
        </div>
      </div>
    </div>
  );
}
