import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataTable } from "../../components/DataTable";
import type { ColumnDef } from "@tanstack/react-table";

interface TestRow {
  id: number;
  name: string;
  score: number;
}

const columns: ColumnDef<TestRow>[] = [
  { accessorKey: "name", header: "Name" },
  { accessorKey: "score", header: "Score" },
];

const data: TestRow[] = [
  { id: 1, name: "Alpha", score: 90 },
  { id: 2, name: "Beta", score: 85 },
  { id: 3, name: "Gamma", score: 95 },
];

describe("DataTable", () => {
  it("should render a table with headers", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
  });

  it("should render all data rows", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
  });

  it("should have cream header background", () => {
    render(<DataTable columns={columns} data={data} />);
    const thead = screen.getByText("Name").closest("thead");
    expect(thead?.className).toContain("bg-brand-cream");
  });

  it("should have slate header text", () => {
    render(<DataTable columns={columns} data={data} />);
    const th = screen.getByText("Name").closest("th");
    expect(th?.className).toContain("text-brand-slate");
  });

  it("should have mist border on rows", () => {
    render(<DataTable columns={columns} data={data} />);
    const row = screen.getByText("Alpha").closest("tr");
    expect(row?.className).toContain("border-brand-mist");
  });

  it("should show sort icon on sortable columns", () => {
    render(<DataTable columns={columns} data={data} />);
    const sortIcons = document.querySelectorAll("svg");
    expect(sortIcons.length).toBeGreaterThan(0);
  });

  it("should call onRowClick when row is clicked", () => {
    const onClick = vi.fn();
    render(<DataTable columns={columns} data={data} onRowClick={onClick} />);
    fireEvent.click(screen.getByText("Alpha").closest("tr")!);
    expect(onClick).toHaveBeenCalledWith(data[0]);
  });

  it("should have cursor-pointer on rows when onRowClick is provided", () => {
    render(
      <DataTable columns={columns} data={data} onRowClick={() => {}} />,
    );
    const row = screen.getByText("Alpha").closest("tr");
    expect(row?.className).toContain("cursor-pointer");
  });

  it("should have rounded-card border on container", () => {
    const { container } = render(
      <DataTable columns={columns} data={data} />,
    );
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("rounded-card");
    expect(wrapper.className).toContain("border-brand-mist");
  });
});
