import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IMPORT_BACKUP_PREFIX, STORAGE_KEY, defaultConfig } from "./config";
import App from "./App";

vi.mock("./bridge", () => ({
  EngineBridge: class {
    init = vi.fn().mockResolvedValue({ version: "3.2.0", config_version: 2, methods: [] });
    terminate = vi.fn();
    resolveAnalysis = vi.fn();
  },
}));

function fileFor(value: unknown): File {
  return new File([JSON.stringify(value)], "config.json", { type: "application/json" });
}

describe("App configuration workflow", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps web onboarding state under the web platform object", () => {
    render(<App />);
    expect(screen.getByRole("dialog", { name: "从一次攻击，到整场遭遇" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始使用" }));
    expect(screen.queryByRole("dialog", { name: "从一次攻击，到整场遭遇" })).not.toBeInTheDocument();
    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as ReturnType<typeof defaultConfig> | null;
    if (persisted) expect(persisted.web.onboarding_seen).toBe(true);
  });

  it("backs up, confirms, replaces and can undo one import", async () => {
    const current = defaultConfig();
    current.web.onboarding_seen = true;
    current.targets[0].name = "导入前目标";
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    const next = defaultConfig();
    next.web.onboarding_seen = true;
    next.targets[0].name = "导入后目标";
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [fileFor(next)] } });
    expect(await screen.findByText(/配置导入成功/)).toBeInTheDocument();
    const backupKey = Object.keys(localStorage).find((key) => key.startsWith(IMPORT_BACKUP_PREFIX));
    expect(backupKey).toBeTruthy();
    expect(JSON.parse(localStorage.getItem(backupKey!)!).targets[0].name).toBe("导入前目标");
    fireEvent.click(screen.getByRole("button", { name: "撤销本次导入" }));
    expect(screen.getByText(/已撤销本次导入/)).toBeInTheDocument();
    await waitFor(() => expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).targets[0].name).toBe("导入前目标"));
  });

  it("rejects a future config before confirmation or backup", async () => {
    const current = defaultConfig();
    current.web.onboarding_seen = true;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    const confirm = vi.spyOn(window, "confirm");
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [fileFor({ config_version: 99 })] } });
    expect(await screen.findByText(/导入失败，当前配置未改变/)).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    expect(Object.keys(localStorage).some((key) => key.startsWith(IMPORT_BACKUP_PREFIX))).toBe(false);
  });
});
