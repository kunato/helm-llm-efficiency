from collections import defaultdict
from dataclasses import dataclass, InitVar, field
from itertools import combinations_with_replacement, product
import math
from math import comb  # type: ignore
import numpy as np
import numpy.typing as npt
import random
import sympy
from sympy import Symbol, Poly, diff
from sympy.parsing.sympy_parser import standard_transformations, implicit_multiplication_application
from typing import List, Optional, Tuple, Dict, Union

from .adapter import AdapterSpec, Adapter, ADAPT_GENERATION
from .adapter_service import AdapterService
from .scenario import Scenario, Instance, Reference, TRAIN_SPLIT, TEST_SPLIT, CORRECT_TAG
from proxy.remote_service import RemoteService
from common.authentication import Authentication


import pdb


def get_test_adapter_service() -> AdapterService:
    return AdapterService(RemoteService("test"), Authentication("test"))


SOLUTION_TAG: str = "solution"
CLASS_TAG: str = "class"
Range = List[Tuple[int, int]]

SYMPY_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


def generate_terms(degree: int, num_variables: int) -> List[List[int]]:
    """Lists out multisets corresponding to all possible terms up to degree `degree` and `num_variables` variables.
    """
    return sum(
        [
            list(map(lambda _: list(_), combinations_with_replacement(range(num_variables), d)))
            for d in reversed(range(degree + 1))
        ],
        [],
    )


def get_powers(terms: List[List[int]]) -> List[List[Tuple[int, int]]]:
    return list(map(lambda _: list(zip(*np.unique(_, return_counts=True))), terms))


def sympy_power_to_power(power: Tuple[int, ...]) -> List[Tuple[int, int]]:
    return [(idx, exp) for idx, exp in enumerate(power) if exp]


def stringify_terms(terms: List[List[int]], variable_names: List[str] = list("xyz")) -> List[str]:
    """Formatting utility for multisets.
    """

    def stringify_power(index: int, degree: int) -> str:
        """Helper formatting utility for powers.
        """
        var = variable_names[index]
        if degree == 0:
            return ""
        if degree == 1:
            return var
        return f"{var}^{degree}"

    powers = get_powers(terms)
    return list(map(lambda _: "".join([stringify_power(*el) for el in _]), powers))


@dataclass
class Polynomial:
    """A simple polynomial class over the integers that supports evaluation and pretty-printing.
    """

    degree: int
    num_variables: int
    coeffs: InitVar[Union[List[int], npt.NDArray[np.int64]]] = None
    terms: List[List[int]] = field(init=False)

    def __post_init__(self, coeffs: List[int]):
        self.terms = generate_terms(self.degree, self.num_variables)
        self.coeffs = np.array(coeffs)

    def eval(self, vals: List[int]):
        return np.dot(self.coeffs, np.array(list(map(lambda _: np.prod(np.array(vals).__getitem__(_)), self.terms))))

    def __str__(self):
        def stringify_monomial(coeff: int, term: str) -> Optional[str]:
            if coeff == 0:
                return None
            if coeff == 1:
                return term or str(coeff)
            if coeff == -1:
                return f"-{term}" if term else "-1"
            return f"{coeff}{term}"

        monomials = [stringify_monomial(c, x) for c, x in zip(self.coeffs, stringify_terms(self.terms))]
        monomials = [m for m in monomials if m]
        return " + ".join(monomials).replace(" + -", " - ")

    @classmethod
    def from_string(cls, expr_str: str, degree: int, num_variables: int):
        expr = sympy.parse_expr(expr_str.replace("^", "**"), transformations=SYMPY_TRANSFORMATIONS)
        poly = Poly(expr, list(expr.free_symbols))
        return sympy_poly_to_poly(poly, degree, num_variables)


def sympy_poly_to_poly(poly: Poly, degree: int, num_variables: int) -> Polynomial:
    terms = poly.terms()
    all_terms = generate_terms(degree, num_variables)
    all_powers = get_powers(all_terms)
    coeffs_dict = defaultdict(int, {tuple(sympy_power_to_power(power)): coeff for power, coeff in terms})
    coeffs = [coeffs_dict[tuple(_)] for _ in all_powers]
    return Polynomial(degree=degree, num_variables=num_variables, coeffs=coeffs)


def generate_polynomial(
    degree: int,
    num_variables: int,
    range_coeffs: Range,  # inclusive
    seed: Optional[int] = None,
    strict_degree=True,
    strict_variables=True,
    strict_constant=True,
) -> Polynomial:
    """Sample the coefficients (A, B, ...) of the polynomial equation y = ... + A x + B.
    A generic method used by the function class-specific methods below.

    Args:
        strict_degree (bool): if True, require `rel` to have degree strictly equal to `degree`
        strict_variables (bool): if True, require `rel` to use exactly `num_variables`
        strict_constant (bool): if True, require the constant (ie. term of degree 0) to be non-zero
    Returns:
        `rel` (Polynomial)
    """
    MAX_ATTEMPTS = 100
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    count = 0
    terms = generate_terms(degree, num_variables)
    while count < MAX_ATTEMPTS:
        done = True
        coeffs = [random.randint(r[0], r[1]) for r in range_coeffs]
        if strict_constant and coeffs[-1] == 0:
            done = False
        if strict_degree and not sum(coeffs[: comb(degree + num_variables - 1, num_variables - 1)]):
            done = False
        if strict_variables:
            for idx in range(num_variables):
                vals = np.zeros(num_variables)
                vals[idx] = 1
                res = np.dot(coeffs[:-1], np.array(list(map(lambda _: np.prod(vals.__getitem__(_)), terms[:-1]))))
                if not res:
                    done = False
                    break
        if done:
            break
        count += 1
        if count >= MAX_ATTEMPTS:
            raise ValueError(
                "Failed to sample valid polynomial equation within "
                + f"{MAX_ATTEMPTS} attempts from ranges {str(range_coeffs)}."
            )
    return Polynomial(degree=degree, num_variables=num_variables, coeffs=coeffs)


def generate_linear(range_coeffs: Range) -> Polynomial:
    return generate_polynomial(
        degree=1,
        num_variables=1,
        range_coeffs=range_coeffs,
        strict_degree=True,
        strict_variables=True,
        strict_constant=True,
    )


def generate_parabola(range_coeffs: Range) -> Polynomial:
    return generate_polynomial(
        degree=2,
        num_variables=1,
        range_coeffs=range_coeffs,
        strict_degree=True,
        strict_variables=True,
        strict_constant=True,
    )


def generate_plane(range_coeffs: Range) -> Polynomial:
    return generate_polynomial(
        degree=1,
        num_variables=2,
        range_coeffs=range_coeffs,
        strict_degree=True,
        strict_variables=True,
        strict_constant=True,
    )


def generate_paraboloid(range_coeffs: Range) -> Polynomial:
    return generate_polynomial(
        degree=2,
        num_variables=2,
        range_coeffs=range_coeffs,
        strict_degree=True,
        strict_variables=True,
        strict_constant=True,
    )


def generate_rotated_translated_paraboloid(range_coeffs: Range) -> Polynomial:
    """Unused.
    """
    do_sample = True
    while do_sample:
        coeffs_0 = generate_plane(range_coeffs).coeffs
        coeffs_1 = generate_plane(range_coeffs).coeffs
        mat = np.array([coeffs_0, coeffs_1,])
        if np.linalg.matrix_rank(mat) == 2:
            do_sample = False
    x = Symbol("x")
    y = Symbol("y")
    xprime = coeffs_0[0] * x + coeffs_0[1] * y + coeffs_0[2]
    yprime = coeffs_1[0] * x + coeffs_1[1] * y + coeffs_1[2]
    expr = xprime ** 2 + yprime ** 2
    poly = Poly(expr, [x, y])
    return sympy_poly_to_poly(poly, 2, 2)


def distance_linear(point: List[int], rel_str: str):
    """
    Returns the minimum distance from the given point to the relation given by `rel_str` which has the form:
    A x - y + B = 0
    """
    relation_type = "linear"
    degree: int = RELTYPE_INFO[relation_type].degree
    num_variables: int = RELTYPE_INFO[relation_type].num_variables
    rel = Polynomial.from_string(rel_str.split(" = ")[-1], degree, num_variables)
    A = rel.coeffs[0]
    B = -1
    C = rel.coeffs[1]
    x, y = point
    return float(abs((A * x + B * y + C)) / (math.sqrt(A ** 2 + B ** 2)))


def distance_parabola(point: List[int], rel_str: str, TOL: float = 1e-10):
    """
    Returns the minimum distance from the given point to the relation given by `rel_str` which has the form:
    y = A x^2 + B x + C
    """
    rel_str = rel_str.split(" = ")[-1]
    expr = sympy.parse_expr(rel_str.replace("^", "**"), transformations=SYMPY_TRANSFORMATIONS)
    poly = sympy.Poly(expr, list(expr.free_symbols))
    x = list(expr.free_symbols)[0]
    x0, y0 = point
    dist = (x - x0) ** 2 + (poly - y0) ** 2
    deriv = sympy.diff(dist, x)
    try:
        sols = sympy.solve(deriv, x)
    except ZeroDivisionError:
        # This shouldn't happen, but has happened for a prior implementation of
        # `distance_paraboloid`, so catch it conservatively:
        print("Failed to compute minimum distance.")
        # import pdb, pdb.set_trace()
        return float(0.0)
    dist_vals = list(map(lambda _: sympy.N(dist.eval(_)), sols))
    try:
        dist_val = min([sympy.re(_) for _ in dist_vals if abs(sympy.im(_)) < TOL and sympy.re(_) >= 0])
    except ValueError:
        # A real solution should exist, but if not (eg. numerical error exceeds TOL):
        print("Failed to compute minimum distance.")
        # import pdb, pdb.set_trace()
        return float(0.0)
    return float(dist_val)


def distance_plane(point: List[int], rel_str: str):
    """
    Returns the minimum distance from the given point to the relation given by `rel_str` which has the form:
    A x + B y - z + C = 0
    """
    relation_type = "plane"
    degree: int = RELTYPE_INFO[relation_type].degree
    num_variables: int = RELTYPE_INFO[relation_type].num_variables
    rel = Polynomial.from_string(rel_str.split(" = ")[-1], degree, num_variables)
    A = rel.coeffs[0]
    B = rel.coeffs[1]
    C = -1
    D = rel.coeffs[2]
    x, y, z = point
    d = abs((A * x + B * y + C * z + D))
    e = math.sqrt(A ** 2 + B ** 2 + C ** 2)
    return float(d / e)


def distance_paraboloid(point: List[int], rel_str: str, TOL: float = 1e-10):
    """
    Returns the minimum distance from the given point to the relation given by `rel_str` which has the form:
    z = A x^2 + B x y + C y^2 + D x + E y + F
    Uses method of Lagrange multipliers.
    """
    rel_str = rel_str.split(" = ")[-1]
    expr = sympy.parse_expr(rel_str.replace("^", "**"), transformations=SYMPY_TRANSFORMATIONS)
    x, y = list(expr.free_symbols)
    if x.name == "y":
        x, y = y, x
    z = Symbol("z")
    x0, y0, z0 = point
    f = (x - x0) ** 2 + (y - y0) ** 2 + (z - z0) ** 2
    g = z - expr
    if abs(g.subs([(x, x0), (y, y0), (z, z0)])) < TOL:
        return float(0.0)
    λ = Symbol("λ")
    # The code below is meant to be equivalent to
    # `sols = sympy.solve([eq_x, eq_y, eq_z, g], [x, y, z, λ])`
    # but sympy.solve was failing to find any solution on many inputs,
    # so this breaks it down for the special case of `f - λ g` which is at most quadratic.
    eq_x = diff(f, x) - λ * diff(g, x)
    eq_y = diff(f, y) - λ * diff(g, y)
    eq_z = diff(f, z) - λ * diff(g, z)
    sols_x = sympy.solve([eq_x], [x, λ])
    sols_y = sympy.solve([eq_y], [y, λ])
    sols_z = sympy.solve([eq_z], [z, λ])
    try:
        sols_xyz = [
            [lst[sym]] if isinstance(lst, dict) else [_[0] for _ in lst]
            for sym, lst in zip([x, y, z], [sols_x, sols_y, sols_z])
        ]
        sols_λλλ = [
            [λ] if isinstance(lst, dict) else [_[1] for _ in lst]
            for sym, lst in zip([x, y, z], [sols_x, sols_y, sols_z])
        ]
        sols_λ = list(product(*sols_xyz))
        vals_λλλ = list(product(*sols_λλλ))
        sols = []
        for sol_xyz, val_λ in zip(sols_λ, vals_λλλ):
            sol_x, sol_y, sol_z = sol_xyz
            sol_λ1, sol_λ2, sol_λ3 = val_λ
            sol_x = sol_x.subs(λ, sol_λ1).subs(λ, sol_λ2).subs(λ, sol_λ3)
            sol_y = sol_y.subs(λ, sol_λ1).subs(λ, sol_λ2).subs(λ, sol_λ3)
            sol_z = sol_z.subs(λ, sol_λ1).subs(λ, sol_λ2).subs(λ, sol_λ3)
            g_λ = g.subs([(x, sol_x), (y, sol_y), (z, sol_z)]).subs(λ, sol_λ1).subs(λ, sol_λ2).subs(λ, sol_λ3)
            # TODO
            sym = list(g_λ.free_symbols)[0]
            vals = [sympy.N(_) for _ in sympy.solveset(g_λ, sym)]
            sols.extend([(sol_x.subs(sym, _), sol_y.subs(sym, _), sol_z.subs(sym, _)) for _ in vals])
    except ZeroDivisionError:
        # This shouldn't happen, but has happened for a prior implementation of
        # `distance_paraboloid`, so catch it conservatively:
        print("Failed to compute minimum distance.")
        pdb.set_trace()
        return float(0.0)
    poly_f = sympy.Poly(f, [x, y, z])
    try:
        dist_vals = list(map(lambda _: sympy.N(poly_f.eval(_)), sols))
    except sympy.polys.polyerrors.UnificationFailed:
        pdb.set_trace()
    try:
        dist_val = min([sympy.re(_) for _ in dist_vals if abs(sympy.im(_)) < TOL and sympy.re(_) >= 0])
    except ValueError:
        # A real solution should exist, but if not (eg. numerical error exceeds TOL):
        print([eq_x, eq_y, eq_z, g])
        print(sols)
        pdb.set_trace()
        return float(0.0)
    return float(dist_val)


def select_ranges(
    num_train: int, num_test: int, dim: int, overlap: bool = True, nonnegative_only: bool = False
) -> Tuple[Range, Range]:
    """
    Choose disjoint intervals from which to sample points, where
    the test points lie within a region bounded by the region
    that the train points are sampled from.
    """
    choices: npt.NDArray[np.int64] = np.array([0, 1, 2, 5, 10, 20, 50, 100, 200])

    def select_index(lst: npt.NDArray[np.int64], val: int) -> int:
        return list((lst - val) >= 0).index(True)

    def construct_range(index: int, dim: int) -> List[Tuple[int, int]]:
        if nonnegative_only:
            return [(0, choices[index]) for _ in range(dim)]
        return [(-choices[index], choices[index]) for _ in range(dim)]

    if nonnegative_only:
        num_points = (choices + 1) ** dim  # list of ints
    else:
        num_points = (2 * choices + 1) ** dim  # list of ints

    if overlap:
        train_index = test_index = select_index(num_points, num_train + num_test)
    else:
        test_index = select_index(num_points, num_test)
        train_index = select_index(num_points - num_points[test_index], num_train)

    test_range = construct_range(test_index, dim)
    train_range = construct_range(train_index, dim)
    return (train_range, test_range)


@dataclass(frozen=True)
class RelationTypeInfo:
    name: str
    degree: int
    num_variables: int
    range: Range
    example_coeffs: List[int]


RELTYPE_INFO: Dict[str, RelationTypeInfo] = {
    "linear": RelationTypeInfo(
        name="linear", degree=1, num_variables=1, range=[(1, 5), (1, 5)], example_coeffs=[2, 5]
    ),  # 2x + 5
    "parabola": RelationTypeInfo(
        # parabolas with axis of symmetry to the left of the origin
        name="parabola",
        degree=2,
        num_variables=1,
        range=[(1, 2), (0, 2), (1, 5)],
        example_coeffs=[1, 0, 2],
    ),  # x^2 + 2
    "plane": RelationTypeInfo(
        name="plane", degree=1, num_variables=2, range=[(1, 5), (1, 5), (1, 5)], example_coeffs=[2, 1, 5]
    ),  # 2x + y + 5
    "paraboloid": RelationTypeInfo(
        # axis-aligned ellipsoid paraboloids only, ie. of the form z = A x^2 + B y^2 + C
        name="paraboloid",
        degree=2,
        num_variables=2,
        range=[(1, 2), (0, 1), (1, 2), (0, 0), (0, 0), (1, 5)],
        example_coeffs=[2, 0, 1, 0, 0, 2],
    ),  # 2x^2 + y^2 + 2
}


# MODE_INFO = {  # Testing purposes
#     "example": {"num_function_train": 1, "num_function_test": 1, "num_train": 10, "num_test": 1,},
#     "standard": {"num_function_train": 1, "num_function_test": 1, "num_train": 10, "num_test": 1,},
#     "function": {"num_function_train": 2, "num_function_test": 2, "num_train": 2, "num_test": 1,},
# }


MODE_INFO = {
    "example": {"num_function_train": 1, "num_function_test": 1, "num_train": 100, "num_test": 100,},
    "standard": {"num_function_train": 1, "num_function_test": 1, "num_train": 100, "num_test": 100,},
    "function": {
        "num_function_train": 1000,
        "num_function_test": 1000,  # don't bother excluding from train set
        "num_train": 100,
        "num_test": 1,
    },
}


def get_var(dim: int, variable_names=list("xyz")):
    return variable_names[dim - 1]


def get_dataset_header(
    dim: int, variable_names: List[str] = list("xyz"), delimeter: str = ", ", output_prefix: str = ", "
):
    return delimeter.join(variable_names[: dim - 1]) + output_prefix + variable_names[dim - 1]


def get_numeracy_adapter_spec(
    max_train_instances: int, max_eval_instances: int, dim: int, delimeter: str = ", ", **kwargs
) -> AdapterSpec:
    return AdapterSpec(
        **{
            **{
                "method": ADAPT_GENERATION,
                "instructions": get_dataset_header(dim, delimeter=delimeter, output_prefix=", "),
                "max_train_instances": max_train_instances,
                "max_eval_instances": max_eval_instances,
                "num_outputs": 1,
                "num_train_trials": 1,
                # "model": "ai21/j1-jumbo",
                # "model": "ai21/j1-large",
                "model": "openai/davinci",
                # "model": "openai/curie",
                # "model": "openai/babbage",
                # "model": "openai/ada",
                "temperature": 0,
                "stop_sequences": ["\n"],
                "max_tokens": 20,
                "input_prefix": "",
                "output_prefix": ", ",
                "block_prefix": "\n",
            },
            **kwargs,
        }
    )  # enable override


class NumeracyScenario(Scenario):
    """
    A task that asks the model to induce an unknown polynomial at a point given a set of function evaluations.
    Unlike pre-existing tasks testing arithmetic, this task attempts to test a deeper notion of numeracy
    which the model cannot rely purely on rote memorization of standard tables of arithmetic operations
    in order to succeed on and which intuitively occurs as a implicit subroutine in broader contexts.

    Decomposes into 4 function classes:
    - linear                    (1 degree,  1 variable)
    - parabola                  (2 degrees, 2 variables)
    - plane                     (1 degree,  2 variables)
    - (ellipsoid) paraboloid    (2 degrees, 2 variables)

        with coefficients drawn from restricted ranges
        (see dict `RELTYPE_INFO`), and
        where {parabola, paraboloid} have nonnegative domains,
        ie. the right ray of the x-axis or upper-right
        quadrant of the plane resp. so that the model cannot
        rely on symmetry.

    and independently 2 + 1 modes:
    - standard
        - A single dataset corresponding to the same polynomial
    - function
        - Multiple datasets, where each dataset instance corresponds to
        an independently sampled polynomial belonging to the same class.
    and
    - example
        - A single dataset corresponding to the same fixed representative for each class.

    If `overlap` is `True`:
        Train and test datapoints are drawn from the same rectilinear region
        centered at the origin (see function `select_ranges`),
        making sure to exclude the training set from the test set.
    Otherwise:
        Train datapoints are drawn from a rectilinear border region while
        test datapoints are drawn from a disjoint rectilinear interior region,
        centered at the origin (see function `select_ranges`).

    Example prompt for `relation_type=parabola,mode=function` with `num_function_train=num_function_test=num_train=2`:
        x,y
        1,4
        -1,2
        0,2

        x,y
        -1,0
        1,20
        0,8

        x,y
        -1,7
        1,11
        0,
    """

    name = "numeracy"
    description = "polynomial induction"
    tags: List[str] = []
    RELTYPES: List[str] = ["linear", "parabola", "plane", "paraboloid"]
    MODES: List[str] = ["example", "standard", "function"]

    def __init__(
        self,
        relation_type: str = "linear",
        mode: str = "function",
        delimiter: str = ", ",
        seed: Optional[int] = None,
        overlap: bool = True,  # whether the in-context and eval points are drawn from the same region
        sort_vals: bool = False,  # whether to sort the in-context examples
    ):
        assert relation_type in NumeracyScenario.RELTYPES
        assert mode in NumeracyScenario.MODES
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self.relation_type = relation_type
        self.mode = mode
        self.delimiter = delimiter
        self.seed = seed
        self.overlap = overlap
        self.sort_vals = sort_vals

        self.degree: int = RELTYPE_INFO[relation_type].degree
        self.num_variables: int = RELTYPE_INFO[relation_type].num_variables
        self.range_coeffs = RELTYPE_INFO[relation_type].range
        self.dim = self.num_variables + 1

        self.num_function_train = MODE_INFO[mode]["num_function_train"]
        self.num_function_test = MODE_INFO[mode]["num_function_test"]
        self.num_train = MODE_INFO[mode]["num_train"]
        self.num_test = MODE_INFO[mode]["num_test"]

    def get_instances(self) -> List[Instance]:
        train_range, test_range = select_ranges(
            num_train=100,
            num_test=100,
            dim=self.num_variables,  # not a typo
            overlap=self.overlap,
            nonnegative_only=self.relation_type in ["parabola", "paraboloid"],
        )
        #               train_range = test_range:
        #               -------------------------
        # linear:       [(-100, 100)]
        # parabola:     [(0, 200)]
        # plane:        [(-10, 10), (-10, 10)]
        # paraboloid:   [(0, 20), (0, 20)]

        test_vals = list(product(*[range(r[0], r[1] + 1) for r in test_range]))
        if self.overlap:
            train_vals = test_vals
        else:
            train_vals = list(set(product(*[range(r[0], r[1] + 1) for r in train_range])) - set(test_vals))
        if self.sort_vals:
            train_vals = list(sorted(train_vals))
        if self.num_variables == 2:
            test_vals = list(filter(lambda _: _[0] <= _[1], test_vals))
            train_vals = list(filter(lambda _: _[0] <= _[1], train_vals))

        def generate_datapoint(rel: Polynomial, vals: List[int]) -> Tuple[List[str], str]:
            y = rel.eval(vals)
            return list(map(str, vals)), str(y)

        def generate_datapoint_instances_for_split(rel, idxs, eval_vals, split):
            instances = []
            for idx in idxs:
                vals = eval_vals[idx]
                str_vals, y = generate_datapoint(rel, vals)
                input = self.delimiter.join(str_vals)
                output = y
                var = get_var(self.dim)
                solution = f"{var} = {rel}"
                references = [
                    Reference(output=output, tags=[CORRECT_TAG]),
                    Reference(output=solution, tags=[SOLUTION_TAG]),
                    Reference(output=self.relation_type, tags=[CLASS_TAG]),
                ]
                instance = Instance(input=input, references=references, split=split)
                instances.append(instance)
            return instances

        def generate_datapoint_instances(rel: Polynomial):
            train_idxs = list(np.random.choice(range(len(train_vals)), self.num_train, replace=False))
            if self.sort_vals:
                train_idxs = list(sorted(train_idxs))
            if self.overlap:
                all_test_idxs = list(set(range(len(test_vals))) - set(train_idxs))
            else:
                all_test_idxs = list(range(len(test_vals)))
            test_idxs = np.random.choice(all_test_idxs, self.num_test, replace=False)

            train_instances = generate_datapoint_instances_for_split(rel, train_idxs, train_vals, TRAIN_SPLIT)
            test_instances = generate_datapoint_instances_for_split(rel, test_idxs, test_vals, TEST_SPLIT)
            instances = train_instances + test_instances
            return instances

        def generate_dataset():
            generate_func = globals()[f"generate_{self.relation_type}"]
            rel = generate_func(self.range_coeffs)
            instances = generate_datapoint_instances(rel)
            return instances

        def generate_datasets(num_instances: int, split: str):
            spec = get_numeracy_adapter_spec(self.num_train, self.num_test, self.dim, self.delimiter)
            service = get_test_adapter_service()
            adapter = Adapter(spec, service)
            outer_spec = get_numeracy_adapter_spec(
                self.num_train, self.num_test, self.dim, instructions="", block_prefix="\n\n", delimeter=self.delimiter,
            )
            outer_adapter = Adapter(outer_spec, service)
            instances = []
            for idx in range(num_instances):
                datapoint_instances = generate_dataset()
                train_instances = datapoint_instances[: self.num_train]
                eval_instances = datapoint_instances[self.num_train :]
                dataset_instances = []
                for idx in range(self.num_test):
                    eval_instance = eval_instances[idx]
                    input = adapter.construct_prompt(train_instances, eval_instance)
                    input = input[: -len(spec.output_prefix.rstrip())]  # strip output_prefix
                    references = eval_instance.references
                    dataset_instance = Instance(input=input, references=references, split=split)  # split doesn't matter
                    dataset_instances.append(dataset_instance)

                input = outer_adapter.construct_prompt(dataset_instances[:-1], dataset_instances[-1])
                input = input[: -len(spec.output_prefix.rstrip())]  # strip output_prefix
                references = dataset_instances[-1].references
                instance = Instance(input=input, references=references, split=split)
                instances.append(instance)

            return instances

        def generate_instances():
            generate_func = globals()[f"generate_{self.relation_type}"]
            if self.mode == "example":
                coeffs = RELTYPE_INFO[self.relation_type].example_coeffs
                rel = Polynomial(self.degree, self.num_variables, coeffs)
                return generate_datapoint_instances(rel)
            if self.mode == "standard":
                rel = generate_func(self.range_coeffs)
                return generate_datapoint_instances(rel)
            if self.mode == "function":
                return generate_datasets(self.num_function_train, TRAIN_SPLIT) + generate_datasets(
                    self.num_function_test, TEST_SPLIT
                )

        return generate_instances()
