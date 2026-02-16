import * as Form from "@radix-ui/react-form";
import { Eye, EyeOff } from "lucide-react";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { CONTROL_NEW_USER } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { useGetRoles, useGetUsers } from "../../controllers/API/queries/auth";
import type {
  inputHandlerEventType,
  UserInputType,
  UserManagementType,
} from "../../types/components";
import type { Users } from "../../types/api";
import BaseModal from "../baseModal";

export default function UserManagementModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  index,
  onConfirm,
  asChild,
}: UserManagementType) {
  const [pwdVisible, setPwdVisible] = useState(false);
  const [confirmPwdVisible, setConfirmPwdVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState(data?.password ?? "");
  const [username, setUserName] = useState(data?.username ?? "");
  const [confirmPassword, setConfirmPassword] = useState(data?.password ?? "");
  const [isActive, setIsActive] = useState(data?.is_active ?? false);
  const [selectedRole, setSelectedRole] = useState(
    data?.role ?? "business_user",
  );
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);
  const [departmentAdmins, setDepartmentAdmins] = useState<Users[]>([]);
  const [departmentAdminEmail, setDepartmentAdminEmail] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentAdminError, setDepartmentAdminError] = useState("");
  const [isDeptAdminLoading, setIsDeptAdminLoading] = useState(false);
  const { mutate: mutateGetRoles } = useGetRoles();
  const { mutate: mutateGetUsers } = useGetUsers({});
  const [inputState, setInputState] = useState<UserInputType>(CONTROL_NEW_USER);
  const { userData } = useContext(AuthContext);
  const deptAdminFetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  useEffect(() => {
    if (open) {
      if (!data) {
        resetForm();
      } else {
        setUserName(data.username);
        setIsActive(data.is_active);
        const nextRole = data.role ?? "business_user";
        setSelectedRole(nextRole);
        setDepartmentAdminEmail(data.department_admin_email ?? "");
        setDepartmentName(data.department_name ?? "");
        setDepartmentAdminError("");

        handleInput({ target: { name: "username", value: data.username } });
        handleInput({ target: { name: "is_active", value: data.is_active } });
        handleInput({ target: { name: "role", value: nextRole } });
      }
    }
  }, [open, data]);

  useEffect(() => {
    if (open) {
      mutateGetRoles(undefined, {
        onSuccess: (roles) => {
          const roleNames = (roles || []).map((r) => r.name);
          const fallbackRoles = [
            "super_admin",
            "department_admin",
            "developer",
            "business_user",
          ];
          const merged = roleNames.length > 0 ? roleNames : fallbackRoles;
          const withSelected = merged.includes(selectedRole)
            ? merged
            : [...merged, selectedRole];
          setAvailableRoles(withSelected);
        },
        onError: () => {
          // Fallback roles if API fails
          const fallbackRoles = ["super_admin", "department_admin", "developer", "business_user"];
          setAvailableRoles(fallbackRoles);
        },
      });
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (userData?.role !== "super_admin") return;
    setIsDeptAdminLoading(true);
    mutateGetUsers(
      { skip: 0, limit: 200, role: "department_admin" },
      {
        onSuccess: (res) => {
          setDepartmentAdmins(res?.users ?? []);
        },
        onError: () => {
          setDepartmentAdmins([]);
        },
        onSettled: () => {
          setIsDeptAdminLoading(false);
        },
      },
    );
  }, [open, userData?.role]);

  useEffect(() => {
    return () => {
      if (deptAdminFetchTimer.current) {
        clearTimeout(deptAdminFetchTimer.current);
      }
    };
  }, []);

  function resetForm() {
    setPassword("");
    setUserName("");
    setConfirmPassword("");
    setIsActive(false);
    setSelectedRole("business_user");
    setDepartmentAdminEmail("");
    setDepartmentName("");
    setDepartmentAdminError("");
    setInputState(CONTROL_NEW_USER);
  }

  function handleRoleChange(selectedRole: string) {
    setSelectedRole(selectedRole);
    handleInput({ target: { name: "role", value: selectedRole } });
    setAvailableRoles((prev) => {
      if (!prev || prev.length === 0) return prev;
      return prev.includes(selectedRole) ? prev : [...prev, selectedRole];
    });
    if (selectedRole === "department_admin") {
      setDepartmentAdminEmail("");
      setDepartmentAdminError("");
    }
  }

  // Helper function to format role for display
  function formatRoleDisplay(role: string) {
    return role.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  }

  const effectiveRole = selectedRole || "business_user";
  const isSuperAdmin = userData?.role === "super_admin";
  const isDepartmentAdminCreator = userData?.role === "department_admin";
  const isCreatingDepartmentAdmin = effectiveRole === "department_admin";
  const requiresDepartmentAdminSelection =
    isSuperAdmin && !isCreatingDepartmentAdmin;
  const rolesToRender =
    availableRoles.length > 0
      ? Array.from(new Set([...availableRoles, effectiveRole].filter(Boolean)))
      : ["super_admin", "department_admin", "developer", "business_user"];

  const departmentAdminOptions = useMemo(
    () =>
      departmentAdmins.map((admin) => ({
        email: admin.username,
        role: admin.role,
      })),
    [departmentAdmins],
  );

  function validateDepartmentAdminSelection(): boolean {
    if (!requiresDepartmentAdminSelection) return true;
    if (!departmentAdminEmail) {
      setDepartmentAdminError("Please select a department admin.");
      return false;
    }
    const exists = departmentAdminOptions.some(
      (admin) =>
        admin.email.toLowerCase() === departmentAdminEmail.toLowerCase(),
    );
    if (!exists) {
      setDepartmentAdminError("Please add department admin first.");
      return false;
    }
    setDepartmentAdminError("");
    return true;
  }

  function fetchDepartmentAdminsByQuery(value: string) {
    if (!requiresDepartmentAdminSelection) return;
    if (deptAdminFetchTimer.current) {
      clearTimeout(deptAdminFetchTimer.current);
    }
    deptAdminFetchTimer.current = setTimeout(() => {
      setIsDeptAdminLoading(true);
      mutateGetUsers(
        { skip: 0, limit: 50, role: "department_admin", q: value || undefined },
        {
          onSuccess: (res) => {
            setDepartmentAdmins(res?.users ?? []);
          },
          onError: () => {
            setDepartmentAdmins([]);
          },
          onSettled: () => {
            setIsDeptAdminLoading(false);
          },
        },
      );
    }, 300);
  }

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <IconComponent
          name={icon}
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root
          onSubmit={(event) => {
            if (password !== confirmPassword) {
              event.preventDefault();
              return;
            }
            const submitRequiresDepartmentAdminSelection =
              userData?.role === "super_admin" && effectiveRole !== "department_admin";
            if (submitRequiresDepartmentAdminSelection && !validateDepartmentAdminSelection()) {
              event.preventDefault();
              return;
            }
            const submitData = {
              ...inputState,
              username,
              is_active: isActive,
              role: effectiveRole,
            };
            
            // Only include password if it's provided
            if (password) {
              submitData.password = password;
            }

            if (isCreatingDepartmentAdmin) {
              submitData.department_name = departmentName;
              submitData.department_admin_email = "";
            } else if (isDepartmentAdminCreator) {
              submitData.department_admin_email = userData?.username || "";
              submitData.department_name =
                (userData as any)?.department_name || "";
            } else if (requiresDepartmentAdminSelection) {
              submitData.department_admin_email = departmentAdminEmail;
            }
            
            resetForm();
            onConfirm(1, submitData);
            setOpen(false);
            event.preventDefault();
          }}
        >
          <div className="grid gap-5">
            <Form.Field name="username">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                }}
              >
                <Form.Label className="data-[invalid]:label-invalid">
                  Username{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
              </div>
              <Form.Control asChild>
                <input
                  onChange={({ target: { value } }) => {
                    handleInput({ target: { name: "username", value } });
                    setUserName(value);
                  }}
                  value={username}
                  className="primary-input"
                  required
                  placeholder="Username"
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your username
              </Form.Message>
            </Form.Field>

            <div className="flex flex-row">
              <div className="mr-3 basis-1/2">
                <Form.Field
                  name="password"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid flex">
                      Password{" "}
                      {!data && (
                        <span className="ml-1 mr-1 font-medium text-destructive">
                          *
                        </span>
                      )}
                      {pwdVisible && (
                        <Eye
                          onClick={() => setPwdVisible(!pwdVisible)}
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                      {!pwdVisible && (
                        <EyeOff
                          onClick={() => setPwdVisible(!pwdVisible)}
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                    </Form.Label>
                  </div>
                  <Form.Control asChild>
                    <input
                      onChange={({ target: { value } }) => {
                        handleInput({ target: { name: "password", value } });
                        setPassword(value);
                      }}
                      value={password}
                      className="primary-input"
                      required={data ? false : true}
                      type={pwdVisible ? "text" : "password"}
                      placeholder={data ? "Leave blank to keep current password" : ""}
                    />
                  </Form.Control>

                  <Form.Message className="field-invalid" match="valueMissing">
                    Please enter a password
                  </Form.Message>

                  {password != confirmPassword && (
                    <Form.Message className="field-invalid">
                      Passwords do not match
                    </Form.Message>
                  )}
                </Form.Field>
              </div>

              <div className="basis-1/2">
                <Form.Field
                  name="confirmpassword"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid flex">
                      Confirm password{" "}
                      {!data && (
                        <span className="ml-1 mr-1 font-medium text-destructive">
                          *
                        </span>
                      )}
                      {confirmPwdVisible && (
                        <Eye
                          onClick={() =>
                            setConfirmPwdVisible(!confirmPwdVisible)
                          }
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                      {!confirmPwdVisible && (
                        <EyeOff
                          onClick={() =>
                            setConfirmPwdVisible(!confirmPwdVisible)
                          }
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                    </Form.Label>
                  </div>
                  <Form.Control asChild>
                    <input
                      onChange={(input) => {
                        setConfirmPassword(input.target.value);
                      }}
                      value={confirmPassword}
                      className="primary-input"
                      required={data ? false : true}
                      type={confirmPwdVisible ? "text" : "password"}
                      placeholder={data ? "Leave blank to keep current password" : ""}
                    />
                  </Form.Control>
                  <Form.Message className="field-invalid" match="valueMissing">
                    Please confirm your password
                  </Form.Message>
                </Form.Field>
              </div>
            </div>
            
            <div className="flex gap-8">
              <Form.Field name="is_active">
                <div>
                  <Form.Label className="data-[invalid]:label-invalid mr-3">
                    Active
                  </Form.Label>
                  <Form.Control asChild>
                    <Checkbox
                      value={isActive}
                      checked={isActive}
                      id="is_active"
                      className="relative top-0.5"
                      onCheckedChange={(value) => {
                        handleInput({ target: { name: "is_active", value } });
                        setIsActive(value);
                      }}
                    />
                  </Form.Control>
                </div>
              </Form.Field>
              
              <Form.Field name="role">
                <div className="flex flex-col">
                  <Form.Label className="data-[invalid]:label-invalid mb-2">
                    Role{" "}
                    <span className="font-medium text-destructive">*</span>
                  </Form.Label>
                  <Form.Control asChild>
                    <select
                      defaultValue={effectiveRole}
                      name="role"
                      onChange={(e) => handleRoleChange(e.target.value)}
                      className="primary-input cursor-pointer"
                      required
                    >
                      {rolesToRender.map((r) => (
                        <option key={r} value={r}>
                          {formatRoleDisplay(r)}
                        </option>
                      ))}
                    </select>
                  </Form.Control>
                </div>
              </Form.Field>
            </div>

            {isCreatingDepartmentAdmin && (
              <Form.Field name="department_name">
                <div className="flex flex-col">
                  <Form.Label className="data-[invalid]:label-invalid mb-2">
                    Department Name{" "}
                    <span className="font-medium text-destructive">*</span>
                  </Form.Label>
                  <Form.Control asChild>
                    <input
                      onChange={({ target: { value } }) => {
                        setDepartmentName(value);
                      }}
                      value={departmentName}
                      className="primary-input"
                      required
                      placeholder="Department name"
                    />
                  </Form.Control>
                </div>
              </Form.Field>
            )}

            {requiresDepartmentAdminSelection && (
              <Form.Field name="department_admin_email">
                <div className="flex flex-col">
                  <Form.Label className="data-[invalid]:label-invalid mb-2">
                    Department Admin Email{" "}
                    <span className="font-medium text-destructive">*</span>
                  </Form.Label>
                  <Form.Control asChild>
                    <input
                      value={departmentAdminEmail}
                      onChange={(e) => {
                        const value = e.target.value;
                        setDepartmentAdminEmail(value);
                        setDepartmentAdminError("");
                        fetchDepartmentAdminsByQuery(value);
                      }}
                      onBlur={() => {
                        validateDepartmentAdminSelection();
                      }}
                      className="primary-input"
                      required
                      placeholder="Type to search department admins"
                    />
                  </Form.Control>
                  <div className="mt-2 max-h-40 overflow-y-auto rounded-md border bg-background">
                    {isDeptAdminLoading && (
                      <div className="px-3 py-2 text-xs text-muted-foreground">
                        Loading...
                      </div>
                    )}
                    {!isDeptAdminLoading &&
                      departmentAdmins.map((admin) => (
                        <button
                          type="button"
                          key={admin.id}
                          onClick={() => {
                            setDepartmentAdminEmail(admin.username);
                            setDepartmentAdminError("");
                          }}
                          className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted"
                        >
                          <span className="truncate">{admin.username}</span>
                          <span className="ml-2 text-xs text-muted-foreground">
                            {formatRoleDisplay(admin.role)}
                          </span>
                        </button>
                      ))}
                    {!isDeptAdminLoading &&
                      departmentAdmins.length === 0 &&
                      departmentAdminEmail && (
                        <div className="px-3 py-2 text-xs text-muted-foreground">
                          Please add department admin first.
                        </div>
                      )}
                  </div>
                  {departmentAdminError && (
                    <div className="mt-1 text-xs text-destructive">
                      {departmentAdminError}
                    </div>
                  )}
                </div>
              </Form.Field>
            )}
          </div>

          <div className="float-right">
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
              }}
              className="mr-3"
            >
              {cancelText}
            </Button>

            <Form.Submit asChild>
              <Button className="mt-8">{confirmationText}</Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
