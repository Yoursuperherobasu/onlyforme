import { cloneDeep } from "lodash";
import { useContext, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import PaginatorComponent from "@/components/common/paginatorComponent";
import {
  useAddUser,
  useDeleteUsers,
  useGetDepartments,
  useGetOrganizations,
  useGetUsers,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import CustomLoader from "@/customization/components/custom-loader";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import { CheckBoxDiv } from "../../components/ui/checkbox";
import { Input } from "../../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import {
  USER_ADD_ERROR_ALERT,
  USER_ADD_SUCCESS_ALERT,
  USER_DEL_ERROR_ALERT,
  USER_DEL_SUCCESS_ALERT,
  USER_EDIT_ERROR_ALERT,
  USER_EDIT_SUCCESS_ALERT,
} from "../../constants/alerts_constants";
import {
  ADMIN_HEADER_DESCRIPTION,
  ADMIN_HEADER_TITLE,
  PAGINATION_PAGE,
  PAGINATION_ROWS_COUNT,
  PAGINATION_SIZE,
} from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import ConfirmationModal from "../../modals/confirmationModal";
import UserManagementModal from "../../modals/userManagementModal";
import useAlertStore from "../../stores/alertStore";
import type { Users } from "../../types/api";
import type { UserInputType } from "../../types/components";
import type {
  DepartmentListItem,
  OrganizationListItem,
} from "@/controllers/API/queries/auth";


export default function AdminPage() {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [selectedDepartmentId, setSelectedDepartmentId] = useState("");
  const [sortBy, setSortBy] = useState("username");
  const [sortOrder, setSortOrder] = useState("asc");
  const [showFilters, setShowFilters] = useState(false);
  const [activeFilterTab, setActiveFilterTab] = useState<
    "organization" | "department" | "sort"
  >("organization");
  const [departments, setDepartments] = useState<DepartmentListItem[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationListItem[]>([]);

  const [size, setPageSize] = useState(PAGINATION_SIZE);
  const [index, setPageIndex] = useState(PAGINATION_PAGE);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData } = useContext(AuthContext);
  const [totalRowsCount, setTotalRowsCount] = useState(0);

  const { mutate: mutateDeleteUser } = useDeleteUsers();
  const { mutate: mutateUpdateUser } = useUpdateUser();
  const { mutate: mutateAddUser } = useAddUser();
  const { mutate: mutateGetDepartments } = useGetDepartments();
  const { mutate: mutateGetOrganizations } = useGetOrganizations();
  const { permissions, role } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);

  const userList = useRef([]);

  useEffect(() => {
    setTimeout(() => {
      fetchUsers();
    }, 500);
  }, []);

  useEffect(() => {
    mutateGetDepartments(undefined, {
      onSuccess: (items) => setDepartments(Array.isArray(items) ? items : []),
    });
    mutateGetOrganizations(undefined, {
      onSuccess: (items) => setOrganizations(Array.isArray(items) ? items : []),
    });
  }, []);

  const [filterUserList, setFilterUserList] = useState(userList.current);

  const { mutate: mutateGetUsers, isPending, isIdle } = useGetUsers({});

  function normalizeErrorMessages(error: any): string[] {
    const detail = error?.response?.data?.detail;
    if (!detail) return [t("Unknown error")];
    if (typeof detail === "string") return [detail];
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (typeof item === "string") return item;
        if (item?.msg) return String(item.msg);
        try {
          return JSON.stringify(item);
        } catch {
          return String(item);
        }
      });
    }
    if (typeof detail === "object") {
      if (detail?.msg) return [String(detail.msg)];
      try {
        return [JSON.stringify(detail)];
      } catch {
        return [String(detail)];
      }
    }
    return [String(detail)];
  }

  function isAlreadyExistsError(error: any): boolean {
    const detail = error?.response?.data?.detail;
    const messages = [
      typeof detail === "string" ? detail : "",
      error?.response?.data?.message ?? "",
      error?.message ?? "",
    ]
      .join(" ")
      .toLowerCase();
    return (
      messages.includes("already exists") ||
      messages.includes("already registered") ||
      messages.includes("duplicate")
    );
  }

  function fetchUsers({
    pageIndex = index,
    pageSize = size,
    query = inputValue,
    organizationId = selectedOrganizationId,
    departmentId = selectedDepartmentId,
    sortByValue = sortBy,
    sortOrderValue = sortOrder,
  }: {
    pageIndex?: number;
    pageSize?: number;
    query?: string;
    organizationId?: string;
    departmentId?: string;
    sortByValue?: string;
    sortOrderValue?: string;
  } = {}) {
    mutateGetUsers(
      {
        skip: pageSize * (pageIndex - 1),
        limit: pageSize,
        ...(query ? { q: query } : {}),
        ...(organizationId ? { organization_id: organizationId } : {}),
        ...(departmentId ? { department_id: departmentId } : {}),
        ...(sortByValue ? { sort_by: sortByValue } : {}),
        ...(sortOrderValue ? { sort_order: sortOrderValue } : {}),
      },
      {
        onSuccess: (users) => {
          setTotalRowsCount(users["total_count"]);
          userList.current = users["users"];
          setFilterUserList(users["users"]);
        },
        onError: () => {},
      },
    );
  }

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setPageSize(pageSize);
    setPageIndex(pageIndex);

    fetchUsers({ pageIndex, pageSize });
  }

  function resetFilter() {
    setPageIndex(PAGINATION_PAGE);
    setPageSize(PAGINATION_SIZE);
    fetchUsers({ pageIndex: PAGINATION_PAGE, pageSize: PAGINATION_SIZE, query: "" });
  }

  function handleFilterUsers(input: string) {
    setInputValue(input);

    if (input === "") {
      setPageIndex(PAGINATION_PAGE);
      fetchUsers({ pageIndex: PAGINATION_PAGE, query: "" });
    } else {
      setPageIndex(PAGINATION_PAGE);
      fetchUsers({ pageIndex: PAGINATION_PAGE, query: input });
    }
  }

  function handleOrganizationFilterChange(value: string) {
    setSelectedOrganizationId(value);
    setPageIndex(PAGINATION_PAGE);
    fetchUsers({ pageIndex: PAGINATION_PAGE, organizationId: value });
  }

  function handleDepartmentFilterChange(value: string) {
    setSelectedDepartmentId(value);
    setPageIndex(PAGINATION_PAGE);
    fetchUsers({ pageIndex: PAGINATION_PAGE, departmentId: value });
  }

  function handleSortByChange(value: string) {
    setSortBy(value);
    setPageIndex(PAGINATION_PAGE);
    fetchUsers({ pageIndex: PAGINATION_PAGE, sortByValue: value });
  }

  function handleSortOrderChange(value: string) {
    setSortOrder(value);
    setPageIndex(PAGINATION_PAGE);
    fetchUsers({ pageIndex: PAGINATION_PAGE, sortOrderValue: value });
  }

  function handleDeleteUser(user) {
    mutateDeleteUser(
      { user_id: user.id },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_DEL_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_DEL_ERROR_ALERT,
            list: normalizeErrorMessages(error),
          });
        },
      },
    );
  }

  function handleEditUser(userId, user) {
    mutateUpdateUser(
      { user_id: userId, user: user },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: normalizeErrorMessages(error),
          });
        },
      },
    );
  }

  function handleDisableUser(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_active = !check;

    mutateUpdateUser(
      { user_id: userId, user: userEdit },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: normalizeErrorMessages(error),
          });
        },
      },
    );
  }

  function overwriteExistingUser(existingUserId: string, user: UserInputType) {
    return new Promise<void>((resolve, reject) => {
      mutateUpdateUser(
        {
          user_id: existingUserId,
          user: {
            is_active: user.is_active,
            role: user.role,
            ...(user.organization_name
              ? { organization_name: user.organization_name }
              : {}),
            ...(user.organization_description
              ? { organization_description: user.organization_description }
              : {}),
            ...(user.department_name ? { department_name: user.department_name } : {}),
            ...(user.department_id ? { department_id: user.department_id } : {}),
            ...(user.department_admin_email
              ? { department_admin_email: user.department_admin_email }
              : {}),
          } as any,
        },
        {
          onSuccess: () => {
            resolve();
          },
          onError: (updateError) => {
            reject(updateError);
          },
        },
      );
    });
  }

  function addUserAsync(user: UserInputType) {
    return new Promise<void>((resolve, reject) => {
      mutateAddUser(user, {
        onSuccess: () => resolve(),
        onError: (error) => reject(error),
      });
    });
  }

  function getUsersAsync(payload: { skip: number; limit: number; q?: string }) {
    return new Promise<any>((resolve, reject) => {
      mutateGetUsers(payload, {
        onSuccess: (res) => resolve(res),
        onError: (error) => reject(error),
      });
    });
  }

  async function createOrOverwriteUser(user: UserInputType): Promise<void> {
    try {
      await addUserAsync(user);
      return;
    } catch (error) {
      if (!isAlreadyExistsError(error)) {
        throw error;
      }

      const existingUser = (userList.current as Users[]).find(
        (u) =>
          String(u.username || "").toLowerCase() ===
          String(user.username || "").toLowerCase(),
      );

      if (existingUser?.id) {
        await overwriteExistingUser(existingUser.id, user);
        return;
      }

      const res = await getUsersAsync({
        skip: 0,
        limit: 200,
        q: user.username,
      });
      const rows: Users[] = Array.isArray(res)
        ? res
        : Array.isArray(res?.users)
          ? res.users
          : [];
      const matched = rows.find(
        (u) =>
          String(u.username || "").toLowerCase() ===
          String(user.username || "").toLowerCase(),
      );

      if (matched?.id) {
        await overwriteExistingUser(matched.id, user);
        return;
      }

      throw error;
    }
  }

  async function handleNewUser(user: UserInputType) {
    const candidates = (
      Array.isArray(user.usernames) && user.usernames.length > 0
        ? user.usernames
        : [user.username]
    )
      .map((item) => String(item || "").trim())
      .filter(Boolean);

    const usernames = Array.from(new Set(candidates));
    const errors: string[] = [];
    let successCount = 0;

    for (const username of usernames) {
      const payload: UserInputType = { ...user, username };
      delete payload.usernames;
      try {
        await createOrOverwriteUser(payload);
        successCount += 1;
      } catch (error) {
        const normalized = normalizeErrorMessages(error);
        errors.push(`${username}: ${normalized.join(" | ")}`);
      }
    }

    resetFilter();

    if (successCount > 0) {
      setSuccessData({
        title:
          usernames.length > 1
            ? `${successCount} user(s) added/updated successfully.`
            : USER_ADD_SUCCESS_ALERT,
      });
    }

    if (errors.length > 0) {
      setErrorData({
        title: USER_ADD_ERROR_ALERT,
        list: errors,
      });
    }
  }

  // Helper function to format role for display
  function formatRole(role: string) {
    if (!role) return t("N/A");
    return role.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  }

  return (
    <>
      {userData && (
        <div className="admin-page-panel flex h-full flex-col pb-8">
          <div className="main-page-nav-arrangement">
            <span className="main-page-nav-title">
              <IconComponent name="Shield" className="w-6" />
              {t(ADMIN_HEADER_TITLE)}
            </span>
          </div>
          <span className="admin-page-description-text">
            {t(ADMIN_HEADER_DESCRIPTION)}
          </span>
          <div className="flex w-full flex-wrap items-center justify-between gap-4 px-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex w-96 items-center gap-4">
                <Input
                  placeholder={t("Search Username")}
                  value={inputValue}
                  onChange={(e) => handleFilterUsers(e.target.value)}
                />
                {inputValue.length > 0 ? (
                  <div
                    className="cursor-pointer"
                    onClick={() => {
                      setInputValue("");
                      resetFilter();
                    }}
                  >
                    <IconComponent name="X" className="w-6 text-foreground" />
                  </div>
                ) : (
                  <div>
                    <IconComponent
                      name="Search"
                      className="w-6 text-foreground"
                    />
                  </div>
                )}
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setShowFilters(true);
                  setActiveFilterTab("organization");
                }}
              >
                {t("Filters")}
              </Button>
            </div>
            <div>
              <UserManagementModal
                title={t("New User")}
                titleHeader={t("Add a new user")}
                cancelText={t("Cancel")}
                confirmationText={t("Save")}
                icon={"UserPlus2"}
                onConfirm={(index, user) => {
                  handleNewUser(user);
                }}
                asChild
              >
                <Button variant="primary">{t("New User")}</Button>
              </UserManagementModal>
            </div>
          </div>
          {showFilters && (
            <>
              <div
                className="fixed inset-0 z-[60] bg-black/40 transition-opacity"
                onClick={() => setShowFilters(false)}
              />
              <div className="fixed inset-x-0 top-0 z-[70] flex h-full w-full items-start justify-center p-4">
                <div className="flex h-full max-h-[720px] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border bg-background shadow-xl transition-transform">
                  <div className="flex items-center justify-between border-b px-5 py-4">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setShowFilters(false)}
                        className="rounded-md p-1 text-muted-foreground hover:text-foreground"
                        aria-label="Close filters"
                      >
                        <IconComponent name="X" className="w-5" />
                      </button>
                      <h2 className="text-lg font-semibold">{t("Filters")}</h2>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedOrganizationId("");
                        setSelectedDepartmentId("");
                        setSortBy("username");
                        setSortOrder("asc");
                        setPageIndex(PAGINATION_PAGE);
                        fetchUsers({
                          pageIndex: PAGINATION_PAGE,
                          query: inputValue,
                          organizationId: "",
                          departmentId: "",
                          sortByValue: "username",
                          sortOrderValue: "asc",
                        });
                      }}
                      className="text-sm text-primary hover:underline"
                    >
                      {t("Clear Filters")}
                    </button>
                  </div>

                  <div className="flex flex-1 overflow-hidden">
                    <div className="w-40 border-r bg-muted/40 p-3 text-sm">
                      <div className="flex flex-col gap-1">
                        <button
                          onClick={() => setActiveFilterTab("organization")}
                          className={`rounded-md px-3 py-2 text-left ${
                            activeFilterTab === "organization"
                              ? "bg-background font-semibold shadow-sm"
                              : "text-muted-foreground"
                          }`}
                        >
                          {t("Organization")}
                        </button>
                        <button
                          onClick={() => setActiveFilterTab("department")}
                          className={`rounded-md px-3 py-2 text-left ${
                            activeFilterTab === "department"
                              ? "bg-background font-semibold shadow-sm"
                              : "text-muted-foreground"
                          }`}
                        >
                          {t("Department")}
                        </button>
                        <button
                          onClick={() => setActiveFilterTab("sort")}
                          className={`rounded-md px-3 py-2 text-left ${
                            activeFilterTab === "sort"
                              ? "bg-background font-semibold shadow-sm"
                              : "text-muted-foreground"
                          }`}
                        >
                          {t("Sort")}
                        </button>
                      </div>
                    </div>

                    <div className="flex-1 overflow-auto p-5">
                      {activeFilterTab === "organization" && (
                        <div className="space-y-3">
                          <h3 className="text-sm font-semibold">
                            {t("Organization")}
                          </h3>
                          <select
                            value={selectedOrganizationId}
                            onChange={(event) =>
                              handleOrganizationFilterChange(event.target.value)
                            }
                            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                          >
                            <option value="">{t("All Organizations")}</option>
                            {organizations.map((org) => (
                              <option key={org.id} value={org.id}>
                                {org.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {activeFilterTab === "department" && (
                        <div className="space-y-3">
                          <h3 className="text-sm font-semibold">
                            {t("Department")}
                          </h3>
                          <select
                            value={selectedDepartmentId}
                            onChange={(event) =>
                              handleDepartmentFilterChange(event.target.value)
                            }
                            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                          >
                            <option value="">{t("All Departments")}</option>
                            {departments.map((dept) => (
                              <option key={dept.id} value={dept.id}>
                                {dept.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {activeFilterTab === "sort" && (
                        <div className="space-y-6">
                          <div className="space-y-3">
                            <h3 className="text-sm font-semibold">
                              {t("Sort By")}
                            </h3>
                            <select
                              value={sortBy}
                              onChange={(event) =>
                                handleSortByChange(event.target.value)
                              }
                              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                            >
                              <option value="username">{t("Username")}</option>
                              <option value="organization">
                                {t("Organization")}
                              </option>
                              <option value="department">
                                {t("Department")}
                              </option>
                              <option value="role">{t("Role")}</option>
                              <option value="created_at">
                                {t("Created At")}
                              </option>
                              <option value="updated_at">
                                {t("Updated At")}
                              </option>
                            </select>
                          </div>
                          <div className="space-y-3">
                            <h3 className="text-sm font-semibold">
                              {t("Order")}
                            </h3>
                            <select
                              value={sortOrder}
                              onChange={(event) =>
                                handleSortOrderChange(event.target.value)
                              }
                              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                            >
                              <option value="asc">{t("Ascending")}</option>
                              <option value="desc">{t("Descending")}</option>
                            </select>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t bg-background px-5 py-4">
                    <span className="text-xs text-muted-foreground">
                      {t("Results")}: {totalRowsCount}
                    </span>
                    <Button onClick={() => setShowFilters(false)}>
                      {t("Apply")}
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
          {isPending || isIdle ? (
            <div className="flex h-full w-full items-center justify-center">
              <CustomLoader remSize={12} />
            </div>
          ) : userList.current.length === 0 && !isIdle ? (
            <>
              <div className="m-4 flex items-center justify-between text-sm">
                {t("No users registered.")}
              </div>
            </>
          ) : (
            <>
              <div
                className={
                  "m-4 h-fit overflow-x-hidden overflow-y-scroll rounded-md border-2 bg-background custom-scroll" +
                  (isPending ? " border-0" : "")
                }
              >
                <Table className={"table-fixed outline-1"}>
                  <TableHeader
                    className={
                      isPending ? "hidden" : "table-fixed bg-muted outline-1"
                    }
                  >
                    <TableRow>
                      
                      <TableHead className="h-10">{t("Username")}</TableHead>
                      <TableHead className="h-10">{t("Organization")}</TableHead>
                      <TableHead className="h-10">{t("Department")}</TableHead>
                      <TableHead className="h-10">{t("Role")}</TableHead>
                      <TableHead className="h-10">{t("Created By")}</TableHead>
                      <TableHead className="h-10">{t("Active")}</TableHead>
                      <TableHead className="h-10">{t("Created At")}</TableHead>
                      <TableHead className="h-10">{t("Updated At")}</TableHead>
                      <TableHead className="h-10 w-[100px] text-right"></TableHead>
                    </TableRow>
                  </TableHeader>
                  {!isPending && can("view_admin_page") && (
                    
                    <TableBody>
                      {filterUserList.map((user: Users, index) => (
                        
                        <TableRow key={index}>
                          
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={user.username}>
                              <span className="cursor-default">
                                {user.username}
                              </span>
                            </ShadTooltip>
                          </TableCell>
                          
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={user.organization_name || "-"}>
                              <span className="cursor-default">
                                {user.organization_name || "-"}
                              </span>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={user.department_name || "-"}>
                              <span className="cursor-default">
                                {user.department_name || "-"}
                              </span>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={formatRole(user.role)}>
                              <span className="cursor-default">
                                {formatRole(user.role)}
                              </span>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={user.created_by_username || user.creator_email || "-"}>
                              <span className="cursor-default">
                                {user.created_by_username || user.creator_email || "-"}
                              </span>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="relative left-1 truncate py-2 text-align-last-left">
                            <ConfirmationModal
                              size="x-small"
                              title={t("Edit")}
                              titleHeader={`${user.username}`}
                              modalContentTitle={t("Attention!")}
                              cancelText={t("Cancel")}
                              confirmationText={t("Confirm")}
                              icon={"UserCog2"}
                              data={user}
                              index={index}
                              onConfirm={(index, user) => {
                                handleDisableUser(
                                  user.is_active,
                                  user.id,
                                  user,
                                );
                              }}
                            >
                              <ConfirmationModal.Content>
                                <span>
                                  {t("Are you completely confident about the changes you are making to this user?")}
                                </span>
                              </ConfirmationModal.Content>
                              <ConfirmationModal.Trigger>
                                <div className="flex w-fit">
                                  <CheckBoxDiv checked={user.is_active} />
                                </div>
                              </ConfirmationModal.Trigger>
                            </ConfirmationModal>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            {
                              new Date(user.create_at!)
                                .toISOString()
                                .split("T")[0]
                            }
                          </TableCell>
                          <TableCell className="truncate py-2">
                            {
                              new Date(user.updated_at!)
                                .toISOString()
                                .split("T")[0]
                            }
                          </TableCell>
                          <TableCell className="flex w-[100px] py-2 text-right">
                            <div className="flex">
                              
                              <UserManagementModal
                                title={t("Edit")}
                                titleHeader={`${user.id}`}
                                cancelText={t("Cancel")}
                                confirmationText={t("Save")}
                                icon={"UserPlus2"}
                                data={user}
                                index={index}
                                onConfirm={(index, editUser) => {
                                  handleEditUser(user.id, editUser);
                                }}
                              >
                                <ShadTooltip content={t("Edit")} side="top">
                                  <IconComponent
                                    name="Pencil"
                                    className="h-4 w-4 cursor-pointer"
                                  />
                                </ShadTooltip>
                              </UserManagementModal>
                              

                              <ConfirmationModal
                                size="x-small"
                                title={t("Delete")}
                                titleHeader={t("Delete User")}
                                modalContentTitle={t("Attention!")}
                                cancelText={t("Cancel")}
                                confirmationText={t("Delete")}
                                icon={"UserMinus2"}
                                data={user}
                                index={index}
                                onConfirm={(index, user) => {
                                  handleDeleteUser(user);
                                }}
                              >
                                <ConfirmationModal.Content>
                                  <span>
                                    {t("Are you sure you want to delete this user?")}{" "}
                                    {t("This action cannot be undone.")}
                                  </span>
                                </ConfirmationModal.Content>
                                <ConfirmationModal.Trigger>
                                  <IconComponent
                                    name="Trash2"
                                    className="ml-2 h-4 w-4 cursor-pointer"
                                  />
                                </ConfirmationModal.Trigger>
                              </ConfirmationModal>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                    
                  )}
                </Table>
              </div>

              <PaginatorComponent
                pageIndex={index}
                pageSize={size}
                totalRowsCount={totalRowsCount}
                paginate={handleChangePagination}
                rowsCount={PAGINATION_ROWS_COUNT}
              ></PaginatorComponent>
            </>
          )}
        </div>
      )}
    </>
  );
}
