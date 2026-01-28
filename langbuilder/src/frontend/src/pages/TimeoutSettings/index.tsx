import { useState } from "react";
import { Settings, Save, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TimeoutSetting {
  id: string;
  label: string;
  value: string;
  unit: string;
  units: string[];
  description: string;
  type: "input" | "switch";
  checked?: boolean;
}

export default function TimeoutSettings() {
  const [settings, setSettings] = useState<TimeoutSetting[]>([
    {
      id: "session_timeout",
      label: "Session Timeout",
      value: "30",
      unit: "min",
      units: ["min", "hr"],
      description: "Session expiration duration",
      type: "input",
    },
    {
      id: "cookie_timeout",
      label: "Cookie Timeout",
      value: "7",
      unit: "days",
      units: ["days", "hr"],
      description: "Cookie lifetime",
      type: "input",
    },
    {
      id: "persistent_cookie",
      label: "Persistent Cookie",
      value: "",
      unit: "",
      units: [],
      description: "Keep user logged in",
      type: "switch",
      checked: true,
    },
    {
      id: "redis_ttl",
      label: "Redis TTL",
      value: "3600",
      unit: "sec",
      units: ["sec", "min"],
      description: "Default Redis object expiry",
      type: "input",
    },
  ]);

  const [hasChanges, setHasChanges] = useState(false);

  const handleValueChange = (id: string, newValue: string) => {
    setSettings((prev) =>
      prev.map((setting) =>
        setting.id === id ? { ...setting, value: newValue } : setting
      )
    );
    setHasChanges(true);
  };

  const handleUnitChange = (id: string, newUnit: string) => {
    setSettings((prev) =>
      prev.map((setting) =>
        setting.id === id ? { ...setting, unit: newUnit } : setting
      )
    );
    setHasChanges(true);
  };

  const handleSwitchChange = (id: string, checked: boolean) => {
    setSettings((prev) =>
      prev.map((setting) =>
        setting.id === id ? { ...setting, checked } : setting
      )
    );
    setHasChanges(true);
  };

  const handleSave = () => {
    console.log("Saving settings:", settings);
    // TODO: Add API call to save settings
    setHasChanges(false);
  };

  const handleReset = () => {
    // Reset to default values
    setSettings([
      {
        id: "session_timeout",
        label: "Session Timeout",
        value: "30",
        unit: "min",
        units: ["min", "hr"],
        description: "Session expiration duration",
        type: "input",
      },
      {
        id: "cookie_timeout",
        label: "Cookie Timeout",
        value: "7",
        unit: "days",
        units: ["days", "hr"],
        description: "Cookie lifetime",
        type: "input",
      },
      {
        id: "persistent_cookie",
        label: "Persistent Cookie",
        value: "",
        unit: "",
        units: [],
        description: "Keep user logged in",
        type: "switch",
        checked: true,
      },
      {
        id: "redis_ttl",
        label: "Redis TTL",
        value: "3600",
        unit: "sec",
        units: ["sec", "min"],
        description: "Default Redis object expiry",
        type: "input",
      },
    ]);
    setHasChanges(false);
  };

  return (
    <div className="flex h-full w-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <Settings className="h-7 w-7 text-purple-500" />
            <h1 className="text-2xl font-semibold">Timeout Settings</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure system timeouts and session management
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={!hasChanges}
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Defaults
          </Button>
          <Button
            variant="default"
            onClick={handleSave}
            disabled={!hasChanges}
            className="gap-2"
          >
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* Settings Section */}
      <div className="flex-1 overflow-auto p-8">
        <div className="w-full px-2 lg:px-4 xl:px-6">
          <h2 className="mb-6 text-lg font-semibold">Timeouts</h2>

          {/* Settings Table */}
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-6 py-4 text-left text-sm font-medium text-muted-foreground">
                    Setting
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-muted-foreground">
                    Value
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-muted-foreground">
                    Unit
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-muted-foreground">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {settings.map((setting) => (
                  <tr key={setting.id} className="hover:bg-muted/50">
                    {/* Setting Name */}
                    <td className="px-6 py-4">
                      <Label className="font-medium">{setting.label}</Label>
                    </td>

                    {/* Value */}
                    <td className="px-6 py-4">
                      {setting.type === "input" ? (
                        <Input
                          type="number"
                          value={setting.value}
                          onChange={(e) =>
                            handleValueChange(setting.id, e.target.value)
                          }
                          className="w-24 bg-background"
                          min="0"
                        />
                      ) : (
                        <Switch
                          checked={setting.checked}
                          onCheckedChange={(checked) =>
                            handleSwitchChange(setting.id, checked)
                          }
                        />
                      )}
                    </td>

                    {/* Unit */}
                    <td className="px-6 py-4">
                      {setting.units.length > 0 ? (
                        <Select
                          value={setting.unit}
                          onValueChange={(value) =>
                            handleUnitChange(setting.id, value)
                          }
                        >
                          <SelectTrigger className="w-24 bg-background">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {setting.units.map((unit) => (
                              <SelectItem key={unit} value={unit}>
                                {unit}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>

                    {/* Description */}
                    <td className="px-6 py-4">
                      <span className="text-sm text-muted-foreground">
                        {setting.description}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Info Box */}
          <div className="mt-6 rounded-lg border border-border bg-blue-50 p-4 dark:bg-blue-950/20">
            <div className="flex gap-3">
              <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-500 text-white">
                <span className="text-xs font-bold">i</span>
              </div>
              <div className="text-sm">
                <p className="font-medium text-blue-900 dark:text-blue-100">
                  Important
                </p>
                <p className="mt-1 text-blue-800 dark:text-blue-200">
                  Changes to timeout settings will affect new sessions only.
                  Existing active sessions will maintain their current timeout
                  values until they expire.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}