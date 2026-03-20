import { Database } from "lucide-react";

const KnowledgeBaseEmptyState = () => {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="text-center">
        <Database className="mx-auto h-12 w-12 text-muted-foreground/50" />
        <h3 className="mt-4 text-lg font-semibold">No knowledge bases found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Get started by uploading your first knowledge base
        </p>
      </div>
    </div>
  );
};

export default KnowledgeBaseEmptyState;
