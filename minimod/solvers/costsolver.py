from minimod.base.basesolver import BaseSolver
from minimod.utils.exceptions import NotPandasDataframe, MissingColumn
from minimod.utils.summary import OptimizationSummary

from minimod.base.bau_constraint import BAUConstraintCreator


import pandas as pd
import mip
import numpy as np


class CostSolver(BaseSolver):
    def __init__(self, 
                 minimum_benefit=None, 
                 drop_bau = False, 
                 main_constraint_over = None, 
                 **kwargs):

        super().__init__(sense=mip.MINIMIZE, **kwargs)

        if isinstance(minimum_benefit, float) or isinstance(minimum_benefit, int):
            self.minimum_benefit = minimum_benefit
        elif isinstance(minimum_benefit, str):
            # Get sum of benefits for interventions
            self.minimum_benefit = self.bau.create_bau_constraint(
                self._df, minimum_benefit, "discounted_benefits"
            )

        self.bau_df = self.bau.bau_df(
            self._df,
            minimum_benefit,
            [
                self.benefit_col,
                self.cost_col,
                "discounted_benefits",
                "discounted_costs",
            ],
        )
        
        if drop_bau:
            self._df = self._df.drop(minimum_benefit, level=self.intervention_col)

        # Add objective and constraint
        self.model.add_objective(self._objective())
        self.model.add_constraint(self._constraint(), self.minimum_benefit, name = "base_constraint")

    def _objective(self):

        cost = self._df["discounted_costs"]

        # Discounted costs
        return self._discounted_sum_all(cost)

    def _constraint(self):

        benefit = self._df["discounted_benefits"]

        ## Make benefits constraint be at least as large as the one from the minimum benefit intervention
        return self._discounted_sum_all(benefit)

    def fit(self, **kwargs):
        return self._fit(**kwargs)

    def report(self, intervention_groups = False):

        s = OptimizationSummary(self)

        super().report()

        if self.num_solutions == 1:
            obj_values = self.objective_value
        elif self.num_solutions > 1:
            obj_values = self.objective_values

        sum_costs = self.opt_df["opt_costs_discounted"].sum()
        sum_benefits = self.opt_df["opt_benefit_discounted"].sum()

        results = [
            ("Minimum Benefit", self.minimum_benefit),
            ("Objective Bounds", obj_values),
            ("Total Cost", sum_costs),
            ("Total " + self.benefit_title, sum_benefits),
        ]

        s.print_generic(results)
        s.print_ratio(name="Cost per Benefit", num=sum_costs, denom=sum_benefits)

        s.print_grouper(
            name="Total Cost and Benefits over Time",
            data=self.opt_df[["opt_vals", "opt_benefit", "opt_costs"]],
            style="markdown",
        )
        
        print()
        print("Optimal Interventions")
        print()
        opt_chosen = self.opt_df.loc[lambda df: df['opt_vals']>0]['opt_vals']
        
        s.print_df(opt_chosen.unstack(level='time').fillna(0))
        
        if isinstance(intervention_groups, dict):
            opt_chosen_reset = opt_chosen.reset_index()
            for intervention in intervention_groups:
                opt_chosen_reset[intervention_groups[intervention]] \
                    = opt_chosen_reset[self.intervention_col].str.contains(intervention).astype(int)
            
            intervention_grouper_df = (
                opt_chosen_reset
                .drop(columns = [self.intervention_col, 'opt_vals'])
                .set_index([self.space_col, self.time_col])
                .stack()
                .unstack(level=self.time_col)
                )

            s.print_df(intervention_grouper_df)
                
            # Use for later
            # a = intervention_grouper_df.reset_index(level='region')[list(range(1,11))].mul(intervention_grouper_df.reset_index(level='region')['region'], axis='index')
            # b = a.groupby(a.index).agg(list)

        
        
        

