import { Clock, Users } from "lucide-react";
import type { Reservation, TableAssignment } from "../lib/api";

interface Props {
  reservations: Reservation[];          // reservas del día seleccionado
  assignments: TableAssignment[];       // assignments para la hora seleccionada
  selectedHour: string;
  onHourChange: (hour: string) => void;
  onReservationClick: (r: Reservation) => void;
  selectedReservationId?: string | null;
}

export default function HourTimeline({
  reservations,
  assignments,
  selectedHour,
  onReservationClick,
  selectedReservationId,
}: Omit<Props, "onHourChange"> & { onHourChange?: (hour: string) => void }) {
  // Reservas para la hora seleccionada (match exacto o dentro del mismo bloque de hora)
  const hourReservations = reservations.filter(r => {
    const [rH] = r.time.split(":");
    const [sH] = selectedHour.split(":");
    return rH === sH && r.status !== "cancelled";
  });

  const assignedIds = new Set(assignments.map(a => a.reservation_id));
  const unassigned = hourReservations.filter(r => !assignedIds.has(r.reservation_id));
  const assigned = hourReservations.filter(r => assignedIds.has(r.reservation_id));

  const getTableLabel = (r: Reservation) => {
    const a = assignments.find(a => a.reservation_id === r.reservation_id);
    return a ? a.table_id : null;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header: count + auto-assign */}
      <div className="px-3 py-2 border-b border-border space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{selectedHour}</span>
            {" · "}{hourReservations.length} reserva{hourReservations.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Reservation list — unassigned first */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {hourReservations.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">Sin reservas a esta hora</p>
        ) : (
          <>
            {unassigned.length > 0 && (
              <>
                {unassigned.length > 0 && assigned.length > 0 && (
                  <div className="text-xs text-muted-foreground px-2 pt-1 pb-0.5 font-medium">Sin mesa</div>
                )}
                {unassigned.map(r => (
                  <ReservationItem
                    key={r.reservation_id}
                    r={r}
                    tableLabel={null}
                    isSelected={r.reservation_id === selectedReservationId}
                    onClick={() => onReservationClick(r)}
                  />
                ))}
              </>
            )}
            {assigned.length > 0 && (
              <>
                {unassigned.length > 0 && (
                  <div className="text-xs text-muted-foreground px-2 pt-2 pb-0.5 font-medium">Con mesa</div>
                )}
                {assigned.map(r => (
                  <ReservationItem
                    key={r.reservation_id}
                    r={r}
                    tableLabel={getTableLabel(r)}
                    isSelected={r.reservation_id === selectedReservationId}
                    onClick={() => onReservationClick(r)}
                  />
                ))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ReservationItem({
  r,
  tableLabel,
  isSelected,
  onClick,
}: {
  r: Reservation;
  tableLabel: string | null;
  isSelected: boolean;
  onClick: () => void;
}) {
  const statusDot: Record<string, string> = {
    confirmed: "bg-emerald-500",
    seated: "bg-blue-500",
    no_show: "bg-gray-500",
    cancelled: "bg-red-500",
  };

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
        isSelected
          ? "bg-primary/10 border-primary/40 text-foreground"
          : "bg-card border-border hover:border-primary/30 hover:bg-muted/50"
      }`}
    >
      <div className="flex items-start gap-2">
        <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${statusDot[r.status] ?? "bg-gray-400"}`} />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-foreground truncate">{r.guest_name}</p>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-0.5">
              <Clock className="w-3 h-3" />{r.time}
            </span>
            <span className="flex items-center gap-0.5">
              <Users className="w-3 h-3" />{r.party_size}p
            </span>
          </div>
          {tableLabel && (
            <span className="inline-block mt-1 text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">
              {tableLabel}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

