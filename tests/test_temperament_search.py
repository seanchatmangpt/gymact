from __future__ import annotations

import pytest

from gymact.temperament_engineering import (
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
)
from gymact.temperament_search import (
    AxisDesignOption,
    AxisDesignSpace,
    manufacture_design_portfolio,
    pareto_designs,
)


def criteria() -> tuple[MissionCriterion, ...]:
    return (
        MissionCriterion(
            criterion_id="coverage",
            axis_weights=(("exploration", 3.0), ("initiative", 1.0)),
        ),
    )


def spaces() -> tuple[AxisDesignSpace, ...]:
    return (
        AxisDesignSpace(
            axis_id="exploration",
            options=(
                AxisDesignOption(
                    option_id="point",
                    mean=0.5,
                    shape=DistributionShape.POINT,
                    engineering_cost=0.0,
                ),
                AxisDesignOption(
                    option_id="uniform",
                    mean=0.5,
                    spread=0.5,
                    shape=DistributionShape.UNIFORM,
                    engineering_cost=0.2,
                ),
                AxisDesignOption(
                    option_id="adaptive",
                    mean=0.5,
                    spread=0.25,
                    shape=DistributionShape.UNIFORM,
                    cue_slope=0.5,
                    engineering_cost=0.3,
                ),
            ),
        ),
        AxisDesignSpace(
            axis_id="initiative",
            options=(
                AxisDesignOption(
                    option_id="point",
                    mean=0.5,
                    shape=DistributionShape.POINT,
                ),
                AxisDesignOption(
                    option_id="bimodal",
                    mean=0.5,
                    spread=0.25,
                    shape=DistributionShape.BIMODAL,
                    engineering_cost=0.1,
                ),
            ),
        ),
    )


def test_portfolio_preserves_full_cartesian_design_space() -> None:
    portfolio = manufacture_design_portfolio(
        mission_id="mission:coverage",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=criteria(),
        spaces=spaces(),
    )
    assert portfolio.total_cardinality == 6
    assert portfolio.explored_cardinality == 6
    assert not portfolio.truncated
    assert len({candidate.candidate_id for candidate in portfolio.candidates}) == 6


def test_bounded_portfolio_reports_truncation_without_claiming_graph_failure() -> None:
    portfolio = manufacture_design_portfolio(
        mission_id="mission:coverage",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=criteria(),
        spaces=spaces(),
        max_candidates=2,
    )
    assert portfolio.total_cardinality == 6
    assert portfolio.explored_cardinality == 2
    assert portfolio.truncated


def test_missing_mission_relevant_axis_is_refused() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:MISSION_AXIS_MISSING_FROM_DESIGN_SPACE:initiative",
    ):
        manufacture_design_portfolio(
            mission_id="mission:coverage",
            topology=ControlTopology.CENTRALIZED,
            mode=DesignMode.ONLINE_PLANNER_OUTPUT,
            criteria=criteria(),
            spaces=(spaces()[0],),
        )


def test_candidate_objectives_keep_benefit_and_cost_axes_separate() -> None:
    portfolio = manufacture_design_portfolio(
        mission_id="mission:coverage",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=criteria(),
        spaces=spaces(),
    )
    by_options = {candidate.option_ids: candidate for candidate in portfolio.candidates}
    heterogeneous = by_options[
        (("exploration", "uniform"), ("initiative", "bimodal"))
    ]
    assert heterogeneous.objectives.relevant_spread == pytest.approx(0.4375)
    assert heterogeneous.objectives.adaptive_capacity == pytest.approx(0.0)
    assert heterogeneous.objectives.engineering_cost == pytest.approx(0.3)
    assert heterogeneous.objectives.implementation_complexity == 4


def test_pareto_frontier_never_scalarizes_to_one_winner() -> None:
    portfolio = manufacture_design_portfolio(
        mission_id="mission:coverage",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=criteria(),
        spaces=spaces(),
    )
    frontier = pareto_designs(portfolio.candidates)
    assert frontier
    assert all(candidate in portfolio.candidates for candidate in frontier)
    assert not any(
        left.objectives.dominates(right.objectives)
        for left in frontier
        for right in frontier
        if left != right
    )


def test_decentralized_online_mode_stays_refused_through_search() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:DECENTRALIZED_SWARM_REQUIRES_ANTICIPATORY_DESIGN",
    ):
        manufacture_design_portfolio(
            mission_id="mission:coverage",
            topology=ControlTopology.DECENTRALIZED,
            mode=DesignMode.ONLINE_PLANNER_OUTPUT,
            criteria=criteria(),
            spaces=spaces(),
        )
