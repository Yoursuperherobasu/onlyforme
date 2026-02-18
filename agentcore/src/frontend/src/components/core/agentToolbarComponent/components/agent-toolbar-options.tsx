import type { Dispatch, SetStateAction } from "react";
import useAgentStore from "@/stores/agentStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";
import PublishButton from "./publish-button";

type AgentToolbarOptionsProps = {
  open: boolean;
  setOpen: Dispatch<SetStateAction<boolean>>;
  openApiModal: boolean;
  setOpenApiModal: Dispatch<SetStateAction<boolean>>;
};
const AgentToolbarOptions = ({
  open,
  setOpen,
  openApiModal,
  setOpenApiModal,
}: AgentToolbarOptionsProps) => {
  const hasIO = useAgentStore((state) => state.hasIO);

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex h-full w-auto gap-1.5 rounded-sm transition-all">
        <PlaygroundButton
          hasIO={hasIO}
          open={open}
          setOpen={setOpen}
          canvasOpen
        />
        
      </div>
      <div className="flex h-full w-auto gap-1.5 rounded-sm transition-all">
        <PublishButton
          hasIO={hasIO}
          open={open}
          setOpen={setOpen}
          canvasOpen
        />
        
      </div>
      {/* <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      /> */}
    </div>
  );
};

export default AgentToolbarOptions;
