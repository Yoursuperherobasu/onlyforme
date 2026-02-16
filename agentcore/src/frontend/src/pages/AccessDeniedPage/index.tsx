import PageLayout from "@/components/common/pageLayout";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export default function AccessDeniedPage({
  message,
}: {
  message?: string;
}) {
  const navigate = useCustomNavigate();

  return (
    <PageLayout
      backTo={-1}
      title="Access Denied"
      description="You don't have permission to access this page."
    >
      <div className="w-full max-w-none -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="flex h-[70vh] flex-col items-center justify-center gap-4 text-center">
          <div className="text-lg font-semibold text-destructive">
            Permission Required
          </div>
          <div className="text-sm text-muted-foreground">
            {"Please contact your administrator if you need access."}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate(-1)}>
              Go Back
            </Button>
            <Button onClick={() => navigate("/")}>Go Home</Button>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}