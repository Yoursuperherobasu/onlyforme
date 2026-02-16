import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { PUBLISH_BUTTON_NAME } from "@/constants/constants";
import { CustomIOModal } from "@/customization/components/custom-new-modal";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext"; 

interface PublishButtonProps {
  hasIO: boolean;
  open: boolean;
  setOpen: (open: boolean) => void;
  canvasOpen: boolean;
}

const PublishIcon = () => (
  <ForwardedIconComponent
    name="Upload"
    className="h-4 w-4 transition-all"
    strokeWidth={ENABLE_PUBLISH ? 2 : 1.5}
  />
);

const ButtonLabel = () => (
  <span className="hidden md:block">{PUBLISH_BUTTON_NAME}</span>
);

const ActiveButton = () => (
  <div
    data-testid="playground-btn-flow-io"
    className="playground-btn-flow-toolbar hover:bg-accent"
  >
    <PublishIcon />
    <ButtonLabel />
  </div>
);

const DisabledButton = () => (
  <div
    className="playground-btn-flow-toolbar cursor-not-allowed text-muted-foreground duration-150"
    data-testid="playground-btn-flow"
  >
    <PublishIcon />
    <ButtonLabel />
  </div>
);

const PublishButton = ({
  hasIO,
  open,
  setOpen,
  canvasOpen,
}: PublishButtonProps) => {
  const { permissions } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);
  const canPublish = can("edit_flows");

  // If user doesn't have edit_flows permission, show disabled button with no interaction
  if (!canPublish) {
    return (
      <ShadTooltip content="You don't have permission to publish">
        <div className="pointer-events-none">
          <DisabledButton />
        </div>
      </ShadTooltip>
    );
  }

  // If user has permission but flow doesn't have IO, show disabled with different tooltip
  if (!hasIO) {
    return (
      <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
        <div className="pointer-events-none">
          <DisabledButton />
        </div>
      </ShadTooltip>
    );
  }

  // User has permission and flow has IO - show active button
  return (
    <CustomIOModal
      open={open}
      setOpen={setOpen}
      disable={false}
      canvasOpen={canvasOpen}
    >
      <ActiveButton />
    </CustomIOModal>
  );
};

export default PublishButton;