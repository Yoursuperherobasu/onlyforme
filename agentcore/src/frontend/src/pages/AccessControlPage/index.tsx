import { useEffect, useMemo, useState, useCallback, useRef, useContext } from "react";
import PageLayout from "@/components/common/pageLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import CustomLoader from "@/customization/components/custom-loader";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { Permission, Role } from "@/types/api";
import {
  useDeleteRole,
  usePostRole,
  usePutRolePermissions,
} from "@/controllers/API/queries/auth";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { AuthContext } from "@/contexts/authContext";

type PermissionSection = {
  name: string;
  permissionKeys: string[];
  items: Permission[];
};

type PermissionPage = {
  name: string;
  sections: PermissionSection[];
};

const EXCEL_PERMISSION_STRUCTURE: Array<{
  page: string;
  sections: Array<{ name: string; keys: string[] }>;
}> = [
  { page: "Dashboard", sections: [{ name: "Page Access", keys: ["view_dashboard"] }] },
  {
    page: "Projects",
    sections: [
      { name: "Page Access", keys: ["view_projects_page"] },
      {
        name: "Actions",
        keys: ["prod_publish_approval_required", "prod_publish_approval_not_required"],
      },
    ],
  },
  {
    page: "Review & Approval",
    sections: [
      { name: "Page Access", keys: ["view_approval_page"] },
      { name: "Actions", keys: ["view_agent", "view_model", "view_mcp"] },
    ],
  },
  {
    page: "Agent Registry",
    sections: [
      { name: "Page Access", keys: ["view_published_agents"] },
      { name: "Actions", keys: ["copy_agents", "view_only_agent"] },
    ],
  },
  {
    page: "Model Registry",
    sections: [
      { name: "Page Access", keys: ["view_models"] },
      { name: "Actions", keys: ["add_new_model", "request_new_model", "retire_model"] },
    ],
  },
  {
    page: "Agent Control Panel",
    sections: [
      { name: "Page Access", keys: ["view_control_panel"] },
      {
        name: "Actions",
        keys: [
          "view_prod",
          "prod_share_agent",
          "prod_start_stop_agent",
          "prod_enable_disable_agent",
          "view_uat",
          "uat_share_agent",
          "uat_start_stop_agent",
          "uat_enable_disable_agent",
        ],
      },
    ],
  },
  {
    page: "Orchestration Chat",
    sections: [
      { name: "Page Access", keys: ["view_orchastration_page"] },
      { name: "Actions", keys: ["view_uat", "view_prod"] },
    ],
  },
  { page: "Observability", sections: [{ name: "Page Access", keys: ["view_observability_page"] }] },
  { page: "Evaluation", sections: [{ name: "Page Access", keys: ["view_evaluation_page"] }] },
  { page: "Guardrails Catalogue", sections: [{ name: "Page Access", keys: ["view_guardrail_page"] }] },
  { page: "VectorDB Catalogue", sections: [{ name: "Page Access", keys: ["view_vectorDb_page"] }] },
  {
    page: "MCP Servers",
    sections: [
      { name: "Page Access", keys: ["view_mcp_page"] },
      { name: "Actions", keys: ["add_new_mcp", "retire_mcp", "request_new_mcp"] },
    ],
  },
  {
    page: "Knowledge Base Management",
    sections: [
      { name: "Page Access", keys: ["view_knowledge_base"] },
      { name: "Actions", keys: ["add_new_knowledge"] },
    ],
  },
  {
    page: "Platform Configurations",
    sections: [
      { name: "Page Access", keys: ["view_platform_configs"] },
      { name: "Actions", keys: ["edit_platform_configs"] },
    ],
  },
  { page: "Admin Page", sections: [{ name: "Page Access", keys: ["view_admin_page"] }] },
  { page: "Access Control", sections: [{ name: "Page Access", keys: ["view_access_control_page"] }] },
];

const EXCEL_PERMISSION_KEYS = new Set(
  EXCEL_PERMISSION_STRUCTURE.flatMap((page) => page.sections.flatMap((section) => section.keys)),
);

export default function AccessControlPage() {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { getUser } = useContext(AuthContext);

  const { mutate: mutateUpdateRolePermissions, isPending: isSaving } = usePutRolePermissions();
  const { mutate: mutateCreateRole, isPending: isCreating } = usePostRole();
  const { mutate: mutateDeleteRole, isPending: isDeleting } = useDeleteRole();

  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [draftPermissions, setDraftPermissions] = useState<string[]>([]);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");
  const [newRolePermissions, setNewRolePermissions] = useState<string[]>([]);
  const [hasLoadError, setHasLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const hasLoadedRef = useRef(false);

  const selectedRole = useMemo(
    () => roles.find((r) => r.id === selectedRoleId) || null,
    [roles, selectedRoleId]
  );

  // Load permissions and roles
  const loadData = useCallback(async (force = false) => {
    if (hasLoadedRef.current && !force) {
      return;
    }
    if (!force) {
      hasLoadedRef.current = true;
    }
    setHasLoadError(false);
    setIsLoading(true);

    try {
      const [permissionsRes, rolesRes] = await Promise.all([
        api.get(`${getURL("ROLES")}/permissions`),
        api.get(`${getURL("ROLES")}/`),
      ]);

      const permissionsData: Permission[] = permissionsRes?.data ?? [];
      const rolesData: Role[] = rolesRes?.data ?? [];

      console.log("Permissions loaded successfully:", permissionsData);
      console.log("Roles loaded successfully:", rolesData);

      setPermissions(permissionsData.filter((perm) => EXCEL_PERMISSION_KEYS.has(perm.key)));
      setRoles(rolesData);

      if (rolesData.length > 0) {
        setSelectedRoleId(rolesData[0].id);
        setDraftPermissions(rolesData[0].permissions || []);
      }
    } catch (error: any) {
      console.error("Failed to load access control data:", error);
      setHasLoadError(true);
      setErrorData({
        title: "Failed to load roles/permissions",
        list: [error?.message || "Unknown error"],
      });
    } finally {
      setIsLoading(false);
    }
  }, [setErrorData]);

  // Initial data load
  useEffect(() => {
    loadData(false);
  }, [loadData]);

  // Update draft permissions when selected role changes
  useEffect(() => {
    if (selectedRole) {
      setDraftPermissions(selectedRole.permissions || []);
    }
  }, [selectedRole]);

  const permissionPages: PermissionPage[] = useMemo(() => {
    const permissionByKey = new Map(permissions.map((perm) => [perm.key, perm]));
    return EXCEL_PERMISSION_STRUCTURE.map((page) => ({
      name: page.page,
      sections: page.sections
        .map((section) => ({
          name: section.name,
          permissionKeys: section.keys,
          items: section.keys
            .map((key) => permissionByKey.get(key))
            .filter((item): item is Permission => Boolean(item)),
        }))
        .filter((section) => section.items.length > 0),
    })).filter((page) => page.sections.length > 0);
  }, [permissions]);

  const hasChanges = useMemo(() => {
    if (!selectedRole) return false;
    const currentPerms = [...(selectedRole.permissions || [])].sort();
    const draftPerms = [...draftPermissions].sort();
    return JSON.stringify(currentPerms) !== JSON.stringify(draftPerms);
  }, [selectedRole, draftPermissions]);

  const toggleDraftPermission = (key: string, checked: boolean) => {
    setDraftPermissions((prev) =>
      checked ? [...new Set([...prev, key])] : prev.filter((p) => p !== key),
    );
  };

  const toggleNewRolePermission = (key: string, checked: boolean) => {
    setNewRolePermissions((prev) =>
      checked ? [...new Set([...prev, key])] : prev.filter((p) => p !== key),
    );
  };

  const handleSavePermissions = () => {
    if (!selectedRole) return;
    mutateUpdateRolePermissions(
      { role_id: selectedRole.id, permissions: draftPermissions },
      {
        onSuccess: (role) => {
          setRoles((prev) =>
            prev.map((r) => (r.id === role.id ? role : r)),
          );
          setSuccessData({ title: "Permissions updated successfully" });
          getUser();
        },
        onError: (error) => {
          console.error('Failed to update permissions:', error);
          setErrorData({ 
            title: "Failed to update permissions",
            list: [error?.response?.data?.detail || error?.message || "Unknown error"]
          });
        },
      },
    );
  };

  const handleCreateRole = () => {
    if (!newRoleName.trim()) return;
    mutateCreateRole(
      {
        name: newRoleName.trim(),
        description: newRoleDescription.trim() || null,
        permissions: newRolePermissions,
      },
      {
        onSuccess: (role) => {
          setRoles((prev) => [...prev, role]);
          setSelectedRoleId(role.id);
          setDraftPermissions(role.permissions || []);
          setIsCreateOpen(false);
          setNewRoleName("");
          setNewRoleDescription("");
          setNewRolePermissions([]);
          setSuccessData({ title: "Role created successfully" });
          getUser();
        },
        onError: (error) => {
          console.error('Failed to create role:', error);
          setErrorData({
            title: "Failed to create role",
            list: [error?.response?.data?.detail || error?.message || "Unknown error"],
          });
        },
      },
    );
  };

  const handleDeleteRole = (roleId: string) => {
    mutateDeleteRole(
      { role_id: roleId },
      {
        onSuccess: () => {
          setRoles((prev) => {
            const next = prev.filter((r) => r.id !== roleId);
            if (selectedRoleId === roleId) {
              setSelectedRoleId(next[0]?.id || null);
              setDraftPermissions(next[0]?.permissions || []);
            }
            return next;
          });
          setSuccessData({ title: "Role deleted successfully" });
          getUser();
        },
        onError: (error) => {
          console.error('Failed to delete role:', error);
          setErrorData({
            title: "Failed to delete role",
            list: [error?.response?.data?.detail || error?.message || "Unknown error"],
          });
        },
      },
    );
  };

  const renderPermissionHierarchy = (
    selectedKeys: string[],
    onToggle: (key: string, checked: boolean) => void,
  ) => {
    if (permissionPages.length === 0) {
      return (
        <div className="text-sm text-muted-foreground text-center py-6">
          No permissions available.
        </div>
      );
    }

    return (
      <div className="overflow-hidden rounded-md border">
        <div className="grid grid-cols-12 bg-muted/50 px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">
          <div className="col-span-3">Pages</div>
          <div className="col-span-3">Tabs / Sections</div>
          <div className="col-span-6">Permissions / Actions</div>
        </div>
        <div className="max-h-[60vh] overflow-auto">
          {permissionPages.map((page) => (
            <div key={page.name} className="grid grid-cols-12 border-t first:border-t-0">
              <div className="col-span-3 border-r px-3 py-3 text-sm font-semibold">
                {page.name}
              </div>
              <div className="col-span-9">
                {page.sections.map((section) => (
                  <div
                    key={`${page.name}-${section.name}`}
                    className="grid grid-cols-9 border-b last:border-b-0"
                  >
                    <div className="col-span-3 border-r px-3 py-3 text-sm text-muted-foreground">
                      {section.name}
                    </div>
                    <div className="col-span-6 px-3 py-3">
                      <div className="grid grid-cols-1 gap-2">
                        {section.items.map((perm) => (
                          <label
                            key={perm.key}
                            className="flex items-start gap-2 text-sm cursor-pointer"
                          >
                            <Checkbox
                              checked={selectedKeys.includes(perm.key)}
                              onCheckedChange={(checked) =>
                                onToggle(perm.key, Boolean(checked))
                              }
                            />
                            <span>
                              {perm.name}
                              <span className="block text-xs text-muted-foreground font-mono">
                                {perm.key}
                              </span>
                              {perm.description && (
                                <span className="block text-xs text-muted-foreground">
                                  {perm.description}
                                </span>
                              )}
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <PageLayout
      backTo={-1}
      title="Access Control"
      description="Create roles and manage permissions across pages, tabs, and navigation."
    >
      <div className="w-full max-w-none -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        {isLoading ? (
          <div className="flex h-[70vh] items-center justify-center">
            <CustomLoader remSize={10} />
          </div>
        ) : hasLoadError ? (
          <div className="flex h-[70vh] flex-col items-center justify-center gap-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-destructive mb-2">
                Failed to Load Data
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                Unable to load roles and permissions. Please check your connection and try again.
              </p>
            </div>
            <Button onClick={() => loadData(true)} variant="outline">
              Retry
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6">
            {/* Left Panel - Roles List */}
            <div className="col-span-12 lg:col-span-4">
              <div className="flex items-center justify-between pb-3">
                <div className="text-sm font-medium">Roles</div>
                <BaseModal open={isCreateOpen} setOpen={setIsCreateOpen} size="large">
                  <BaseModal.Trigger asChild>
                    <Button variant="primary">New Role</Button>
                  </BaseModal.Trigger>
                  <BaseModal.Header description="Create a role and pick permissions.">
                    New Role
                  </BaseModal.Header>
                  <BaseModal.Content>
                    <div className="flex flex-col gap-4">
                      <div>
                        <div className="mb-1 text-sm font-medium">Role Name</div>
                        <Input
                          value={newRoleName}
                          placeholder="e.g. qa_lead"
                          onChange={(e) => setNewRoleName(e.target.value)}
                        />
                      </div>
                      <div>
                        <div className="mb-1 text-sm font-medium">Description</div>
                        <Input
                          value={newRoleDescription}
                          placeholder="Optional description"
                          onChange={(e) => setNewRoleDescription(e.target.value)}
                        />
                      </div>
                      <div>
                        <div className="mb-2 text-sm font-medium">
                          Permissions
                        </div>
                        {renderPermissionHierarchy(
                          newRolePermissions,
                          toggleNewRolePermission,
                        )}
                      </div>
                    </div>
                  </BaseModal.Content>
                  <BaseModal.Footer
                    submit={{
                      label: "Create Role",
                      loading: isCreating,
                      disabled: !newRoleName.trim(),
                      onClick: handleCreateRole,
                    }}
                  />
                </BaseModal>
              </div>
              <div className="rounded-md border">
                {roles.length === 0 ? (
                  <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                    No roles available. Create one to get started.
                  </div>
                ) : (
                  roles.map((role) => (
                    <div
                      key={role.id}
                      className={`flex items-center justify-between px-3 py-2 text-sm cursor-pointer transition-colors border-b last:border-b-0 ${
                        role.id === selectedRoleId
                          ? "bg-muted"
                          : "hover:bg-muted/40"
                      }`}
                      onClick={() => setSelectedRoleId(role.id)}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{role.name}</div>
                        {role.description && (
                          <div className="text-xs text-muted-foreground truncate">
                            {role.description}
                          </div>
                        )}
                      </div>
                      {!role.is_system && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs ml-2 flex-shrink-0"
                          disabled={isDeleting}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Are you sure you want to delete the role "${role.name}"?`)) {
                              handleDeleteRole(role.id);
                            }
                          }}
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right Panel - Permissions */}
            <div className="col-span-12 lg:col-span-8">
              <div className="flex items-center justify-between pb-3">
                <div className="text-sm font-medium">
                  Permissions for {selectedRole?.name || "-"}
                </div>
                <Button
                  variant="primary"
                  disabled={!hasChanges || isSaving}
                  onClick={handleSavePermissions}
                >
                  {isSaving ? "Saving..." : "Save Changes"}
                </Button>
              </div>
              <div className="rounded-md border p-4">
                {selectedRole ? (
                  renderPermissionHierarchy(draftPermissions, toggleDraftPermission)
                ) : (
                  <div className="text-sm text-muted-foreground text-center py-6">
                    Select a role to view and edit permissions.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  );
}

