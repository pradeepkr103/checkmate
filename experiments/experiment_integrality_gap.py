import argparse
import logging

from experiments.common.definitions import checkmate_data_dir
from experiments.common.graph_plotting import plot_schedule
from checkmate.core.graph_builder import gen_linear_graph
from checkmate.core.enum_strategy import ImposedSchedule
from checkmate.core.solvers.lower_bound_lp import lower_bound_lp_relaxation
from checkmate.core.solvers.strategy_approx_lp import solve_approx_lp_deterministic_sweep
from checkmate.core.solvers.strategy_optimal_ilp import solve_ilp_gurobi


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-layers", "-n", default=16, type=int)
    parser.add_argument(
        "--imposed-schedule", default=ImposedSchedule.FULL_SCHEDULE, type=ImposedSchedule, choices=list(ImposedSchedule)
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Set parameters
    args = parse_args()
    N = args.num_layers
    IMPOSED_SCHEDULE = args.imposed_schedule
    APPROX = False
    EPS_NOISE = 0
    SOLVE_R = False

    # Compute integrality gap for each budget
    for B in reversed(range(4, N + 3)):  # Try several budgets
        g = gen_linear_graph(N)
        scratch_dir = (
            checkmate_data_dir()
            / "scratch_integrality_gap_linear"
            / "{}_layers".format(N)
            / str(IMPOSED_SCHEDULE)
            / "{}_budget".format(B)
        )
        scratch_dir.mkdir(parents=True, exist_ok=True)
        data = []

        logging.error("Skipping Griewank baselines as it was broken in parasj/checkmate#65")
        # griewank = solve_griewank(g, B)

        logging.info("--- Solving LP relaxation for lower bound")
        lb_lp = lower_bound_lp_relaxation(g, B, approx=APPROX, eps_noise=EPS_NOISE, imposed_schedule=IMPOSED_SCHEDULE)
        plot_schedule(lb_lp, False, save_file=scratch_dir / "CHECKMATE_LB_LP.png")

        logging.info("--- Solving ILP")
        ilp = solve_ilp_gurobi(g, B, approx=APPROX, eps_noise=EPS_NOISE, imposed_schedule=IMPOSED_SCHEDULE, solve_r=SOLVE_R)
        ilp_feasible = ilp.schedule_aux_data.activation_ram <= B
        plot_schedule(ilp, False, save_file=scratch_dir / "CHECKMATE_ILP.png")

        integrality_gap = ilp.schedule_aux_data.cpu / lb_lp.schedule_aux_data.cpu
        speedup = ilp.solve_time_s / lb_lp.solve_time_s

        approx_ratio_actual, approx_ratio_ub = float("inf"), float("inf")
        try:
            logging.info("--- Solving deterministic rounting of LP")
            approx_lp_determinstic = solve_approx_lp_deterministic_sweep(
                g, B, approx=APPROX, eps_noise=EPS_NOISE, imposed_schedule=IMPOSED_SCHEDULE
            )
            if approx_lp_determinstic.schedule_aux_data:
                approx_ratio_ub = approx_lp_determinstic.schedule_aux_data.cpu / lb_lp.schedule_aux_data.cpu
                approx_ratio_actual = approx_lp_determinstic.schedule_aux_data.cpu / ilp.schedule_aux_data.cpu
        except Exception as e:
            logging.error("WARN: exception in solve_approx_lp_deterministic")
            logging.exception(e)

        logging.info(
            ">>> N={} B={} ilp_feasible={} lb_lp_feasible={}"
            " integrality_gap={:.3f} approx_ratio={:.3f}-{:.3f}"
            " time_ilp={:.3f} time_lp={:.3f} speedup={:.3f}".format(
                N,
                B,
                ilp.feasible,
                lb_lp.feasible,
                integrality_gap,
                approx_ratio_actual,
                approx_ratio_ub,
                ilp.solve_time_s,
                lb_lp.solve_time_s,
                speedup,
            )
        )
