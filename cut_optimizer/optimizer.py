from __future__ import annotations

from dataclasses import dataclass, field
import math
from collections import Counter
from typing import List, Dict, Optional

# Internally we compute in 0.1mm units to support kerf values like 2.8mm exactly.
SCALE = 10  # 1mm = 10 units (0.1mm per unit)

# 0.5mm expressed in internal 0.1mm units.
HALF_MM_U = 5


# For better packing, we optionally run an exact bounded-knapsack fill on
# "short" stock sticks first (then finish with the fast greedy heuristic).
# This dramatically reduces cases where smaller stock sticks get used
# inefficiently, leaving parts unallocated even though there is plenty of
# leftover material spread across many sticks.
SMALL_STOCK_KNAPSACK_MAX_MM = 4000


def round_up_to_half_mm(mm: float) -> float:
    """Round *up* to the next 0.5mm boundary.

    Examples:
      1000.0 -> 1000.0
      1000.01 -> 1000.5
      1000.5 -> 1000.5
      1000.6 -> 1001.0
    """
    if mm <= 0:
        return 0.0

    # Convert to internal 0.1mm units, rounding *up* to the next 0.1mm,
    # then round *up* again to the next 0.5mm boundary.
    eps = 1e-9
    u_tenth = int(math.ceil(float(mm) * SCALE - eps))
    u_half = int(math.ceil(u_tenth / HALF_MM_U) * HALF_MM_U)
    return u_half / SCALE


def mm_to_u(mm: float) -> int:
    """Convert mm (may include .5 increments) to internal 0.1mm units."""
    return int(round(float(mm) * SCALE))

def u_to_mm_str(u: int) -> str:
    # Render tenths-mm units as a human-friendly mm string (no trailing .0)
    if u % SCALE == 0:
        return str(u // SCALE)
    return f"{u / SCALE:.1f}".rstrip("0").rstrip(".")

@dataclass(frozen=True)
class StockItem:
    # Stored in mm, rounded up to 0.5mm increments at ingest/edit time.
    length_mm: float
    qty: int

@dataclass(frozen=True)
class PartItem:
    # Stored in mm, rounded up to 0.5mm increments at ingest/edit time.
    length_mm: float
    qty: int
    label: str = ""

@dataclass(frozen=True)
class PartInstance:
    length_u: int
    label: str = ""

@dataclass
class StickPlan:
    stock_length_u: int
    parts: List[PartInstance] = field(default_factory=list)

    def used_u(self, kerf_u: int) -> int:
        if not self.parts:
            return 0
        return sum(p.length_u for p in self.parts) + kerf_u * (len(self.parts) - 1)

    def leftover_u(self, kerf_u: int) -> int:
        return self.stock_length_u - self.used_u(kerf_u)

    def can_add(self, part: PartInstance, kerf_u: int) -> bool:
        if part.length_u <= 0:
            return False
        if not self.parts:
            return part.length_u <= self.stock_length_u
        return self.used_u(kerf_u) + kerf_u + part.length_u <= self.stock_length_u

    def add(self, part: PartInstance) -> None:
        self.parts.append(part)

@dataclass
class OptimizeResult:
    plans: List[StickPlan]
    unallocated_parts: List[PartInstance]
    summary: Dict[str, float]

def _expand_parts(parts: List[PartItem]) -> List[PartInstance]:
    out: List[PartInstance] = []
    for p in parts:
        if p.qty > 0 and p.length_mm > 0:
            out.extend([PartInstance(length_u=mm_to_u(p.length_mm), label=p.label or "")] * p.qty)
    return out

def _expand_stock(stock: List[StockItem]) -> List[int]:
    out: List[int] = []
    for s in stock:
        if s.qty > 0 and s.length_mm > 0:
            out.extend([mm_to_u(s.length_mm)] * s.qty)
    return out

def _pick_smallest_fitting_stock(available_stock_u: List[int], required_u: int) -> Optional[int]:
    candidates = [L for L in available_stock_u if L >= required_u]
    return min(candidates) if candidates else None


def _build_result(plans: List[StickPlan], unallocated: List[PartInstance], kerf_u: int) -> OptimizeResult:
    for plan in plans:
        plan.parts.sort(key=lambda p: p.length_u, reverse=True)

    total_stock_used_u = sum(p.stock_length_u for p in plans)
    total_parts_used_u = sum(sum(pp.length_u for pp in p.parts) for p in plans)
    total_kerf_loss_u = sum(max(0, len(p.parts) - 1) * kerf_u for p in plans)
    total_used_with_kerf_u = total_parts_used_u + total_kerf_loss_u
    total_leftover_u = sum(p.leftover_u(kerf_u) for p in plans)

    utilization = (total_used_with_kerf_u / total_stock_used_u * 100.0) if total_stock_used_u else 0.0

    summary: Dict[str, float] = {
        "sticks_used": float(len(plans)),
        "kerf_mm": float(kerf_u) / SCALE,
        "total_stock_used_mm": float(total_stock_used_u) / SCALE,
        "total_parts_mm": float(total_parts_used_u) / SCALE,
        "total_kerf_loss_mm": float(total_kerf_loss_u) / SCALE,
        "total_used_with_kerf_mm": float(total_used_with_kerf_u) / SCALE,
        "total_leftover_mm": float(total_leftover_u) / SCALE,
        "utilization_pct": float(utilization),
        "unallocated_count": float(len(unallocated)),
    }
    return OptimizeResult(plans=plans, unallocated_parts=unallocated, summary=summary)


def _place_parts_greedy(
    plans: List[StickPlan],
    available_stock_u: List[int],
    parts_sorted_desc: List[PartInstance],
    kerf_u: int,
) -> List[PartInstance]:
    """Place parts into existing plans and open new sticks from available_stock_u as needed."""

    unallocated: List[PartInstance] = []

    for part in parts_sorted_desc:
        best_i: Optional[int] = None
        best_leftover_after: Optional[int] = None

        for i, plan in enumerate(plans):
            if plan.can_add(part, kerf_u):
                delta = part.length_u if not plan.parts else (kerf_u + part.length_u)
                leftover_after = plan.leftover_u(kerf_u) - delta
                if best_leftover_after is None or leftover_after < best_leftover_after:
                    best_leftover_after = leftover_after
                    best_i = i

        if best_i is not None:
            plans[best_i].add(part)
            continue

        chosen = _pick_smallest_fitting_stock(available_stock_u, part.length_u)
        if chosen is None:
            unallocated.append(part)
            continue

        available_stock_u.remove(chosen)
        plans.append(StickPlan(stock_length_u=chosen, parts=[part]))

    return unallocated


def _bounded_knapsack_max_fill(cap_u: int, weights_u: List[int], counts: List[int]) -> List[int]:
    """Bounded knapsack (exact DP) maximizing total weight <= cap_u.

    Returns the chosen counts per type.
    """

    if cap_u <= 0 or not weights_u or not counts:
        return [0] * len(weights_u)

    # Binary-split counts into 0-1 items.
    split_w: List[int] = []
    split_type: List[int] = []
    split_qty: List[int] = []

    for ti, (w, c) in enumerate(zip(weights_u, counts)):
        if w <= 0 or c <= 0:
            continue
        k = 1
        while c > 0:
            take = k if k < c else c
            split_w.append(w * take)
            split_type.append(ti)
            split_qty.append(take)
            c -= take
            k *= 2

    if not split_w:
        return [0] * len(weights_u)

    best = [-1] * (cap_u + 1)
    best[0] = 0
    prev_cap = [-1] * (cap_u + 1)
    prev_item = [-1] * (cap_u + 1)

    for idx, w in enumerate(split_w):
        for c in range(cap_u, w - 1, -1):
            b = best[c - w]
            if b == -1:
                continue
            v = b + w
            if v > best[c]:
                best[c] = v
                prev_cap[c] = c - w
                prev_item[c] = idx

    best_val = max(best)
    if best_val <= 0:
        return [0] * len(weights_u)

    c = best.index(best_val)
    chosen = [0] * len(weights_u)
    while c > 0 and prev_item[c] != -1:
        idx = prev_item[c]
        ti = split_type[idx]
        chosen[ti] += split_qty[idx]
        c = prev_cap[c]

    return chosen


def _optimize_knapsack_then_greedy(stock: List[StockItem], parts: List[PartItem], kerf_u: int) -> OptimizeResult:
    """Fallback optimizer:

    1) Pack *short* sticks (<= SMALL_STOCK_KNAPSACK_MAX_MM) using exact bounded-knapsack
       to maximize stick utilization.
    2) Finish with the fast greedy best-fit heuristic for the remaining parts/stock.
    """

    available_stock_u = _expand_stock(stock)
    available_stock_u.sort()

    # Aggregate parts by (length,label) so the DP stays small.
    expanded = _expand_parts(parts)
    counts: Counter[tuple[int, str]] = Counter((p.length_u, p.label) for p in expanded)

    plans: List[StickPlan] = []

    small_threshold_u = SMALL_STOCK_KNAPSACK_MAX_MM * SCALE
    remaining_stock_u: List[int] = []

    # First, pack short sticks optimally.
    for L in available_stock_u:
        if L > small_threshold_u:
            remaining_stock_u.append(L)
            continue

        if not counts:
            # No parts left; keep stock unused.
            continue

        type_keys = list(counts.keys())
        type_counts = [counts[k] for k in type_keys]
        type_weights = [k[0] + kerf_u for k in type_keys]  # transform: add kerf to each part
        cap_u = L + kerf_u  # transformed capacity

        chosen = _bounded_knapsack_max_fill(cap_u=cap_u, weights_u=type_weights, counts=type_counts)
        if not any(chosen):
            # Nothing fits; keep this stock for the greedy stage.
            remaining_stock_u.append(L)
            continue

        stick_parts: List[PartInstance] = []
        for (length_u, label), n_take in zip(type_keys, chosen):
            if n_take <= 0:
                continue
            stick_parts.extend([PartInstance(length_u=length_u, label=label)] * n_take)
            new_count = counts[(length_u, label)] - n_take
            if new_count <= 0:
                del counts[(length_u, label)]
            else:
                counts[(length_u, label)] = new_count

        plans.append(StickPlan(stock_length_u=L, parts=stick_parts))

    # Re-expand remaining parts for the greedy stage.
    remaining_parts: List[PartInstance] = []
    for (length_u, label), qty in counts.items():
        remaining_parts.extend([PartInstance(length_u=length_u, label=label)] * qty)
    remaining_parts.sort(key=lambda p: p.length_u, reverse=True)

    unallocated = _place_parts_greedy(plans=plans, available_stock_u=remaining_stock_u, parts_sorted_desc=remaining_parts, kerf_u=kerf_u)
    return _build_result(plans=plans, unallocated=unallocated, kerf_u=kerf_u)

def optimize_cut_order(stock: List[StockItem], parts: List[PartItem], kerf_mm: float) -> OptimizeResult:
    '''
    Heuristic: First-Fit Decreasing + best-fit placement, with finite stock quantities.

    - Inputs:
      - stock lengths and part lengths are in mm (integers)
      - kerf_mm can be fractional (e.g. 2.8)

    - Internal units:
      - 0.1mm (tenths) integer arithmetic to avoid floating-point surprises.
    '''
    if kerf_mm < 0:
        raise ValueError("kerf_mm must be >= 0")

    kerf_u = int(round(float(kerf_mm) * SCALE))

    # Fast baseline (existing heuristic).
    expanded_parts = _expand_parts(parts)
    expanded_parts.sort(key=lambda p: p.length_u, reverse=True)
    available_stock_u = _expand_stock(stock)

    plans: List[StickPlan] = []
    unallocated = _place_parts_greedy(plans=plans, available_stock_u=available_stock_u, parts_sorted_desc=expanded_parts, kerf_u=kerf_u)
    baseline = _build_result(plans=plans, unallocated=unallocated, kerf_u=kerf_u)

    # If anything is unallocated, attempt a stronger (but still fast) fallback.
    if not baseline.unallocated_parts:
        return baseline

    improved = _optimize_knapsack_then_greedy(stock=stock, parts=parts, kerf_u=kerf_u)

    # Pick the better result.
    if len(improved.unallocated_parts) < len(baseline.unallocated_parts):
        return improved
    if len(improved.unallocated_parts) > len(baseline.unallocated_parts):
        return baseline

    # Tie-breakers: prefer fewer sticks used, then higher utilization.
    if improved.summary.get("sticks_used", 0.0) < baseline.summary.get("sticks_used", 0.0):
        return improved
    if improved.summary.get("sticks_used", 0.0) > baseline.summary.get("sticks_used", 0.0):
        return baseline

    if improved.summary.get("utilization_pct", 0.0) > baseline.summary.get("utilization_pct", 0.0):
        return improved
    return baseline
