"""Headless 3-DOF Planar Arm Forward Kinematics Demo Target for DesktopPilot Testing."""

from __future__ import annotations

import math
from typing import Tuple


def forward_kinematics_3dof(
    l1: float,
    l2: float,
    l3: float,
    theta1_deg: float,
    theta2_deg: float,
    theta3_deg: float,
) -> Tuple[float, float, float]:
    t1 = math.radians(theta1_deg)
    t2 = t1 + math.radians(theta2_deg)
    t3 = t2 + math.radians(theta3_deg)
    x = l1 * math.cos(t1) + l2 * math.cos(t2) + l3 * math.cos(t3)
    y = l1 * math.sin(t1) + l2 * math.sin(t2) + l3 * math.sin(t3)
    phi_deg = math.degrees(t3)
    return (round(x, 4), round(y, 4), round(phi_deg, 4))


if __name__ == "__main__":
    print("End-effector pose (x, y, phi):", forward_kinematics_3dof(100.0, 80.0, 40.0, 30.0, -15.0, 10.0))
