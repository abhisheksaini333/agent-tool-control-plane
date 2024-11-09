import React from "react";
import { RequestRecord, timeLabel } from "./client";
export function Receipt({ request }: { request: RequestRecord }) {
  const receipt = request.receipt;
  if (!receipt) return null;
  const metrics = receipt.output.metrics as Record<string, unknown> | undefined;
  return (
    <section className="receipt-card" aria-label="Execution receipt">
      <p className="eyebrow">VERIFIED EXECUTION</p>
      <h3>{receipt.effect ? "Inventory reserved." : "Tool completed."}</h3>
      {receipt.effect ? (
        <p className="receipt-result">
          <strong>{String(receipt.effect.quantity)}</strong> unit
          {receipt.effect.quantity === 1 ? "" : "s"} of{" "}
          <strong>{String(receipt.effect.sku)}</strong>
          <span>
            {String(receipt.effect.available_after)} units remaining after this
            reservation.
          </span>
        </p>
      ) : (
        <pre>{JSON.stringify(receipt.output.result, null, 2)}</pre>
      )}
      <div className="receipt-facts">
        <span>
          Completed <strong>{timeLabel(receipt.completed_at)}</strong>
        </span>
        <span>
          Attempt <strong>{receipt.attempt}</strong>
        </span>
        {metrics && (
          <>
            <span>
              Worker elapsed{" "}
              <strong>{(Number(metrics.elapsed_ms) / 1000).toFixed(2)}s</strong>
            </span>
            <span>
              Memory limit{" "}
              <strong>
                {Math.round(Number(metrics.memory_bytes) / 1024 / 1024)} MiB
              </strong>
            </span>
          </>
        )}
      </div>
      <p className="small muted">
        Receipt {receipt.id.slice(0, 8)} · This completion record cannot be
        replayed to create another effect.
      </p>
      <details>
        <summary>Full receipt</summary>
        <pre>{JSON.stringify(receipt, null, 2)}</pre>
      </details>
    </section>
  );
}
