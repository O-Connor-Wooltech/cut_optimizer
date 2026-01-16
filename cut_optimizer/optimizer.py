from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import List, Dict, Optional

# Internally we compute in 0.1mm units to support kerf values like 2.8mm exactly.
SCALE = 10  # 1mm = 10 units (0.1mm per unit)

# 0.5mm expressed in internal 0.1mm units.
HALF_MM_U = 5


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

    expanded_parts = _expand_parts(parts)
    expanded_parts.sort(key=lambda p: p.length_u, reverse=True)

    available_stock_u = _expand_stock(stock)

    plans: List[StickPlan] = []
    unallocated: List[PartInstance] = []

    for part in expanded_parts:
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
