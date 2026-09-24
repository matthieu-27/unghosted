/**
 * The editable grid: shadcn data-table recipe (ADR 0004) — TanStack Table v9
 * columns + TanStack Virtual rows, cell selection and typed in-cell editing
 * on shadcn primitives. Cells are focusable and keyboard-activatable
 * (Enter/Space). The full ARIA grid pattern (role=grid + arrow navigation)
 * lands with the accessibility pass — the native table semantics carry M1.
 */

import {
  type CellSelectionState,
  createColumnHelper,
  useTable,
} from '@tanstack/react-table';
import type { Virtualizer } from '@tanstack/react-virtual';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useMemo, useRef, useState } from 'react';
import { CellDisplay, CellEditor } from '@/components/tracker/cell-editors';
import { features } from '@/components/tracker/data-table-features';
import { Button } from '@/components/ui/button';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from '@/components/ui/context-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type {
  ColumnDefinition,
  TrackerOperation,
  TrackerRow,
} from '@/lib/tracker-types';

const ROW_HEIGHT = 32;
const DEFAULT_COLUMN_WIDTH = 140;

// Absolute-positioned rows do not share the header's column grid, so cell
// widths must be pinned explicitly to keep rows aligned with the header.
const totalColumnWidth = (columns: ColumnDefinition[]) =>
  columns.reduce((sum, column) => sum + columnWidth(column), 0);

const columnWidth = (column: ColumnDefinition) =>
  column.width ?? DEFAULT_COLUMN_WIDTH;

const headerWidth = (column: ColumnDefinition | undefined) =>
  column ? columnWidth(column) : DEFAULT_COLUMN_WIDTH;

interface TrackerGridProps {
  columns: ColumnDefinition[];
  rows: TrackerRow[];
  onOperation: (operation: TrackerOperation) => void;
  onAddRow: () => void;
  onDeleteRow: (rowId: string) => void;
  onWriteMail?: (rowId: string) => void;
}

function cellKeyDown(event: React.KeyboardEvent, onSelect: () => void): void {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    onSelect();
  }
}

interface TrackerCellProps {
  column: ColumnDefinition;
  row: TrackerRow;
  editing: boolean;
  onSelect: () => void;
  onOperation: (operation: TrackerOperation) => void;
  onStopEditing: () => void;
}

/** One grid cell: editable cells are focusable + keyboard-activatable, and
 * swap in the type-appropriate editor when selected. */
function TrackerCell({
  column,
  row,
  editing,
  onSelect,
  onOperation,
  onStopEditing,
}: TrackerCellProps) {
  const editable = !column.system && !column.computed;
  const interactions = editable
    ? {
        tabIndex: 0,
        onClick: onSelect,
        onKeyDown: (event: React.KeyboardEvent) => cellKeyDown(event, onSelect),
      }
    : { tabIndex: -1 };
  return (
    <TableCell
      data-editing={editing}
      style={{ width: columnWidth(column) }}
      className="cursor-cell truncate px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring data-[editing=true]:outline-2 data-[editing=true]:outline-ring"
      {...interactions}
    >
      {editing ? (
        <CellEditor
          column={column}
          row={row}
          onCommit={(value) => {
            onOperation({
              op: 'set_cell',
              row_id: row.id,
              column_key: column.key,
              value,
            });
            onStopEditing();
          }}
          onCancel={onStopEditing}
        />
      ) : (
        <CellDisplay column={column} row={row} />
      )}
    </TableCell>
  );
}

interface GridRowsProps {
  virtualizer: Virtualizer<HTMLDivElement, Element>;
  rows: TrackerRow[];
  columns: ColumnDefinition[];
  selectedRowId: string | undefined;
  selectedColumnId: string | undefined;
  onOperation: (operation: TrackerOperation) => void;
  onDeleteRow: (rowId: string) => void;
  onWriteMail?: (rowId: string) => void;
  onCellSelect: (rowId: string, columnKey: string) => void;
  onStopEditing: () => void;
}

/** Virtualized body: each row is absolute-positioned inside the tall body
 * element, with a context menu for row deletion. */
function GridRows({
  virtualizer,
  rows,
  columns,
  selectedRowId,
  selectedColumnId,
  onOperation,
  onDeleteRow,
  onWriteMail,
  onCellSelect,
  onStopEditing,
}: GridRowsProps) {
  return (
    <TableBody
      style={{ height: virtualizer.getTotalSize(), position: 'relative' }}
    >
      {virtualizer.getVirtualItems().map((virtualRow) => {
        const row = rows[virtualRow.index];
        if (!row) return null;
        return (
          <ContextMenu key={row.id}>
            <ContextMenuTrigger
              render={
                <TableRow
                  className="absolute left-0 w-full hover:bg-transparent"
                  style={{
                    top: 0,
                    height: virtualRow.size,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                />
              }
            >
              {columns.map((column) => (
                <TrackerCell
                  key={column.key}
                  column={column}
                  row={row}
                  editing={
                    selectedRowId === row.id && selectedColumnId === column.key
                  }
                  onSelect={() => onCellSelect(row.id, column.key)}
                  onOperation={onOperation}
                  onStopEditing={onStopEditing}
                />
              ))}
            </ContextMenuTrigger>
            <ContextMenuContent>
              {onWriteMail ? (
                <ContextMenuItem onClick={() => onWriteMail(row.id)}>
                  Write first contact
                </ContextMenuItem>
              ) : null}
              <ContextMenuItem
                variant="destructive"
                onClick={() => onDeleteRow(row.id)}
              >
                Delete row
              </ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        );
      })}
    </TableBody>
  );
}

const columnHelper = createColumnHelper<typeof features, TrackerRow>();

/** Row and column keys of the single selected cell, if any. */
function selectionAnchors(selection: CellSelectionState): {
  rowId: string | undefined;
  columnId: string | undefined;
} {
  const selected = selection[0];
  return { rowId: selected?.anchorRowId, columnId: selected?.anchorColumnId };
}

function selectCell(
  setCellSelection: (state: CellSelectionState) => void,
  rowId: string,
  columnKey: string,
) {
  setCellSelection([
    {
      anchorColumnId: columnKey,
      anchorRowId: rowId,
      focusColumnId: columnKey,
      focusRowId: rowId,
    },
  ]);
}

export function TrackerGrid({
  columns,
  rows,
  onOperation,
  onAddRow,
  onDeleteRow,
  onWriteMail,
}: TrackerGridProps) {
  const [cellSelection, setCellSelection] = useState<CellSelectionState>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const tableColumns = useMemo(
    () =>
      columns.map((column) =>
        columnHelper.display({
          id: column.key,
          header: column.label,
          cell: ({ row }) => <CellDisplay column={column} row={row.original} />,
        }),
      ),
    [columns],
  );

  const table = useTable({
    features,
    columns: tableColumns,
    data: rows,
    state: { cellSelection },
    onCellSelectionChange: setCellSelection,
  });

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const selected = cellSelection[0];
  const { rowId: selectedRowId, columnId: selectedColumnId } =
    selectionAnchors(cellSelection);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onAddRow}>
          + Add row
        </Button>
        {selected ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDeleteRow(selected.anchorRowId)}
          >
            Delete row
          </Button>
        ) : null}
      </div>
      <div ref={scrollRef} className="h-[60vh] overflow-auto rounded-md border">
        <Table
          className="table-fixed"
          style={{ width: totalColumnWidth(columns) }}
        >
          <TableHeader className="sticky top-0 z-10 bg-background">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header, index) => (
                  <TableHead
                    key={header.id}
                    scope="col"
                    style={{ width: headerWidth(columns[index]) }}
                    className="truncate border-b px-2 text-left text-xs font-medium"
                  >
                    {String(header.column.columnDef.header)}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <GridRows
            virtualizer={virtualizer}
            rows={rows}
            columns={columns}
            selectedRowId={selectedRowId}
            selectedColumnId={selectedColumnId}
            onOperation={onOperation}
            onDeleteRow={onDeleteRow}
            onWriteMail={onWriteMail}
            onCellSelect={(rowId, columnKey) =>
              selectCell(setCellSelection, rowId, columnKey)
            }
            onStopEditing={() => setCellSelection([])}
          />
        </Table>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Empty tracker. Add a row to start, or paste a listing once the &quot;+
          New application&quot; flow lands.
        </p>
      ) : null}
    </div>
  );
}
