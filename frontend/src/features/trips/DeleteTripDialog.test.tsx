import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Trip } from "../../api/types";
import { DeleteTripDialog } from "./DeleteTripDialog";

const trip = {
  id: "trip-1",
  title: "北京客户拜访",
  summary: { document_count: 4, grand_total_amount: 1180 },
} as Trip;

describe("DeleteTripDialog", () => {
  afterEach(cleanup);

  it("names the destructive scope and only deletes after confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DeleteTripDialog trip={trip} busy={false} error={false} onClose={vi.fn()} onConfirm={onConfirm} />);

    expect(screen.getByRole("dialog", { name: "删除项目" })).toHaveTextContent("北京客户拜访");
    expect(screen.getByRole("dialog", { name: "删除项目" })).toHaveTextContent("4 份文件");
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "确认删除" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("closes with Escape unless deletion is running", () => {
    const onClose = vi.fn();
    const { rerender } = render(<DeleteTripDialog trip={trip} busy={false} error={false} onClose={onClose} onConfirm={vi.fn()} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();

    rerender(<DeleteTripDialog trip={trip} busy error={false} onClose={onClose} onConfirm={vi.fn()} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
