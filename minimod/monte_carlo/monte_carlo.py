from minimod.solvers import Minimod
from minimod.utils.plotting import Plotter
from minimod.utils.summary import OptimizationSummary
from mip import OptimizationStatus

import numpy as np
import pandas as pd
from tqdm import tqdm
from pqdm.processes import pqdm

import matplotlib.pyplot as plt

from functools import reduce
from multiprocessing import Pool
from functools import partial
import matplotlib.ticker as mtick


class MonteCarloMinimod:
    def __init__(
        self,
        solver_type=None,
        data=None,
        intervention_col=None,
        time_col=None,
        space_col=None,
        benefit_mean_col=None,
        benefit_sd_col=None,
        cost_col=None,
        cost_uniform_perc=None,
        pop_weight_col=None,
        **kwargs,
    ):

        print("""Monte Carlo Simulator""")

        self.solver_type = solver_type

        self.data = data.set_index([intervention_col, space_col, time_col])

        self.intervention_col = intervention_col
        self.space_col = space_col
        self.time_col = time_col

        if pop_weight_col is None:
            self.data = self.data.assign(pop_weight_col=1)
            self.pop_weight_col = "pop_weight_col"
        else:
            self.pop_weight_col = pop_weight_col

        self.benefit_mean_col = benefit_mean_col
        self.benefit_sd_col = benefit_sd_col

        if cost_uniform_perc is None:
            self.cost_uniform_perc = 0.2
        else:
            self.cost_uniform_perc = cost_uniform_perc

        self.cost_col = cost_col


    def _construct_benefit_sample(self, seed, data=None, benefit_col = 'benefit_random_draw'):
        """ For normal, it doesn't require transformation, so just return mean and sd"""

        random = np.random.default_rng(seed=seed)
        
        df_mean_sd = data[
            [self.benefit_mean_col, self.benefit_sd_col, self.pop_weight_col]
        ]

        df = df_mean_sd.pipe(self._drop_nan_benefits).assign(
            weight_mean=lambda df: df[self.benefit_mean_col] * df[self.pop_weight_col],
            weight_sd=lambda df: df[self.benefit_sd_col] * df[self.pop_weight_col],
            benefit_random_draw=lambda df: random.normal(
                df["weight_mean"], df["weight_sd"]
            ),
        )

        return df[benefit_col]

    def _construct_cost_sample(self, seed, data=None, cost_col='cost_random_draw'):
        """For costs we assume uniform and deviate by some percentage."""

        random= np.random.default_rng(seed=seed)

        df_costs = data[self.cost_col]
        df_costs_low = (1 - self.cost_uniform_perc) * data[self.cost_col]
        df_costs_high = (1 + self.cost_uniform_perc) * data[self.cost_col]

        df = df_costs.to_frame().assign(
            cost_random_draw=random.uniform(df_costs_low, df_costs_high)
        )

        return df[cost_col]

    def _drop_nan_benefits(self, data):

        df = data.dropna(subset=[self.benefit_sd_col])

        return df

    def _merge_samples(self, benefit_callable, cost_callable,  cost_kwargs, benefit_kwargs):

        benefit_sample = benefit_callable(**benefit_kwargs)
        cost_sample = cost_callable(**cost_kwargs)

        return benefit_sample.to_frame().merge(
            cost_sample, left_index=True, right_index=True
        )
        
    def fit_one_sample(self, 
                       seed,
                       all_space,
                       all_time,
                       space_subset,
                       time_subset,
                       strict,
                       benefit_callable=None,
                       cost_callable=None,
                       cost_kwargs=None,
                       benefit_kwargs=None,
                       **kwargs):
        
        if benefit_callable is None:
            benefit_callable = self._construct_benefit_sample
        if cost_callable is None:
            cost_callable = self._construct_cost_sample

        cost_kwargs_default = {'seed' : seed, 'cost_col' : 'cost_random_draw', 'data' : self.data}
        benefit_kwargs_default = {'seed' : seed, 'benefit_col' : 'benefit_random_draw', 'data' : self.data}
        
        if cost_kwargs is not None:
            cost_kwargs_default.update(cost_kwargs)
        if benefit_kwargs is not None:
            benefit_kwargs_default.update(benefit_kwargs)

                       
        df = self._merge_samples(benefit_callable=benefit_callable,
                                 cost_callable=cost_callable,
                                 benefit_kwargs=benefit_kwargs_default,
                                 cost_kwargs=cost_kwargs_default) 

        minimod = Minimod(solver_type=self.solver_type)(
            data=df,
            intervention_col=self.intervention_col,
            space_col=self.space_col,
            time_col=self.time_col,
            benefit_col=benefit_kwargs_default.get('benefit_col'),
            cost_col=cost_kwargs_default.get('cost_col'),
            all_space=all_space,
            all_time=all_time,
            space_subset=space_subset,
            time_subset=time_subset,
            show_output=False,
            strict=strict,
            benefit_title="Effective Coverage",
            **kwargs,
        )

        minimod.fit()
        
        # Run `minimod.report` to get opt_df for iteration
        # Also save the opt_chosen dataframes in case there are multiple solutions
        
        opt_df_list = []
        
        for i in range(minimod.num_solutions):
            minimod.report(sol_num=i, quiet=True)
            opt_df_list.append(minimod.opt_df)
            
        #TODO: add lowest cost per life saved index into iteration dict
            
        iteration_dict = {
            "status": minimod.status,
            "opt_objective": [df['opt_costs_discounted'].sum() for df in opt_df_list],
            "opt_constraint": [df["opt_benefit_discounted"].sum() for df in opt_df_list],
            "num_vars": minimod.num_cols,
            "constraints": minimod.num_rows,
            "solutions": minimod.num_solutions,
            "num_int": minimod.num_int,
            "num_nz": minimod.num_nz,
            "opt_df": opt_df_list,
            "sense" : minimod.sense,
            "solver_name" : minimod.solver_name,
            "minimum_benefit" : minimod.minimum_benefit,
            "benefit_title" : minimod.benefit_title,
            "bau_draw" : minimod.bau_df
        }
        
        return iteration_dict

    def fit_all_samples(
        self,
        n_jobs = 5,
        N=None,
        all_space=None,
        all_time=None,
        space_subset=None,
        time_subset=None,
        strict=False,
        exception_behavior = 'immediate',
        only_optimal=False,
        benefit_callable=None,
        cost_callable=None,
        benefit_kwargs=None,
        cost_kwargs=None,
        random_seeds = None,
        **kwargs
    ):
        
        if N is None:
            N = 10

        sim_dict = {}


        print(f"""Running with {N} Samples""")
        
        partial_fit_sample = partial(self.fit_one_sample, 
                                     all_space=all_space,
                                     all_time=all_time,
                                     space_subset=space_subset,
                                     time_subset = time_subset,
                                     strict=strict,
                                     benefit_callable=benefit_callable,
                                     cost_callable=cost_callable,
                                     benefit_kwargs=benefit_kwargs,
                                     cost_kwargs=cost_kwargs,
                                     **kwargs)
        
        if random_seeds is None:
            random_seeds = range(N)
                
        sim_dict = pqdm(random_seeds, partial_fit_sample, n_jobs=n_jobs, exception_behaviour=exception_behavior)
        
        sim_df = pd.DataFrame(sim_dict)
        
        self.perc_opt = sim_df["status"].value_counts(normalize=True)[0] * 100

        if only_optimal:
            self.sim_results = sim_df.loc[lambda df: df['status'] == OptimizationStatus.OPTIMAL]
        else:
            self.sim_results = sim_df

        self.N = self.sim_results.shape[0]

        return self.sim_results

    def _all_opt_df(self, sol_filter=None):
        """Appends the dataframe from all simulation iterations together
        """
        #TODO: #28 Allow for concatenation of a combination of solutions, or all
        
        # First get sim_results so that `opt_df` is a series of dataframes
        # Turn list into numpy since it has a `take` method
        
        if sol_filter=='min_cb':
            # Find the solution with the highest benefit/cost ratio
            sol_num_all_opt_df = self.sim_results.assign(best_solution  = lambda df: df.apply(lambda df: (np.array(df['opt_objective'])/np.array(df['opt_constraint'])).argmin(), axis=1),
                                       new_opt_df = lambda df: df.apply(lambda x: x['opt_df'][x['best_solution']], axis=1))
        else:
            sol_num_all_opt_df = self.sim_results.assign(new_opt_df = lambda df: df['opt_df'].apply(lambda x: pd.concat(x)))
        
        all_opt_df = pd.concat(sol_num_all_opt_df.apply(lambda x: x['new_opt_df'].assign(iteration = x.name), axis=1).tolist())

        return all_opt_df

    def _get_intervention_group(self, data, intervention, strict=False):

        
        if strict:
            
            int_group = (
                data
                .loc[lambda df: df.index.
                    get_level_values(level= self.intervention_col)
                    .isin(intervention)]
            )
        
        else:
            int_group = (
                data
                .loc[lambda df: df.index.
                    get_level_values(level= self.intervention_col)
                    .str.contains(intervention)]
            )

        return int_group
    
    def _get_indicator_if_in_intervention(self, name, indicator_spec = None, strict=False):
        
        if indicator_spec is None:
            indicator_spec = 1
        
        return (self._get_intervention_group(self._all_opt_df(), name, strict=strict)
                .reset_index()
                [['opt_vals', 'iteration', self.intervention_col, self.space_col, self.time_col]]
                .groupby('iteration')
                .agg(lambda x: 1 if x.sum() > indicator_spec else 0)
                )

    def report(
        self,
        avg_time=False,
        avg_space=False,
        intervention_group=None,
        indicator_spec = None,
        strict=False
    ):

        avg = self.sim_results.convert_dtypes().mean()

        s = OptimizationSummary(self)

        header = [
            ("MiniMod Solver Results", ""),
            ("Method:", str(self.sim_results['sense'].min())),
            ("Solver:", str(self.sim_results['solver_name'].min())),
            ("Percentage Optimized:", self.perc_opt),
            ("Average Number Solutions Found:", avg["solutions"]),
        ]

        features = [
            ("No. of Variables:", avg["num_vars"]),
            ("No. of Integer Variables:", avg["num_int"]),
            ("No. of Constraints", avg["constraints"]),
            ("No. of Non-zeros in Constr.", avg["num_nz"]),
        ]

        results_benefits = [("Minimum Benefit", self.sim_results.minimum_benefit.mean())]

        stats = [
            ("Statistics for Benefits and Costs", ""),
        ]

        s.print_generic(header, features, results_benefits, stats)

        stats_df = (
            self.sim_results[["opt_objective", "opt_constraint"]]
            .astype(float)
            .describe()
            .round(4)
            .to_markdown()
        )
        print(stats_df)

        if intervention_group is not None:

            s.print_generic([(f"% Appearance of:", "")])

            for i in intervention_group:

                int_group = (self._get_indicator_if_in_intervention(i, 
                                                                    indicator_spec=indicator_spec,
                                                                    strict=strict).sum()/self.N*100)['opt_vals']

                s.print_generic([(f"{i}", f"{int_group}")])

        if avg_time:

            time_df = (
                self._all_opt_df().groupby([self.time_col, "iteration"])
                .sum()
                .groupby(self.time_col)
                .mean()[["opt_benefit", "opt_costs"]]
            )

            s.print_generic([("Mean Benefits and Costs across time", "")])
            print(time_df.to_markdown())

        if avg_space:

            space_df = (
                self._all_opt_df().groupby([self.space_col, "iteration"])
                .sum()
                .groupby(self.space_col)
                .mean()[["opt_benefit", "opt_costs"]]
            )

            s.print_generic([("Mean Benefits and Costs across Regions", "")])
            print(space_df.to_markdown())

    def plot_opt_hist(self, save=None):

        p = Plotter(self)

        costs = "Optimal Costs"
        benefits = self.sim_results['benefit_title'].min()

        if self.solver_type == "costmin":

            objective_title = costs
            constraint_title = benefits

        elif self.solver_type == "benmax":

            objective_title = benefits
            constraint_title = costs


        self.sim_results['opt_constraint2']=self.sim_results['opt_constraint'].apply(lambda x: x[0]/1000)
        self.sim_results['opt_objective2']=self.sim_results['opt_objective'].apply(lambda x: x[0]/1000)

        fig, (benefit_plot, cost_plot) = p._plot_sim_hist(
            data=self.sim_results,
            benefit_col="opt_constraint2",
            cost_col="opt_objective2",
            #benefit_col="opt_constraint",
            #cost_col="opt_objective",
            cost_title=objective_title,
            benefit_title=constraint_title,
            save=save,
        )

        benefit_plot.xaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}'))
        cost_plot.xaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}'))
    
        benefit_plot.set_xlabel("Thousands of Individuals")
        cost_plot.set_xlabel("Thousands of 2019 USD")

        benefit_xlims = benefit_plot.get_xlim()
        benefit_ylims = benefit_plot.get_ylim()

        # Put text at midpoint of y
        text_y = (benefit_ylims[1] - benefit_ylims[0]) / 2

        # offset by 10% of length of x-axis
        text_x = (
            self.sim_results['minimum_benefit'].mean()/1000 + (benefit_xlims[1] - benefit_xlims[0]) * 0.1
        )

        benefit_plot.axvline(self.sim_results['minimum_benefit'].mean()/1000, color="red")
        benefit_plot.text(text_x, text_y, "Mean\nMinimum\nBenefit\nConstraint")
        
        # Get total cost for a draw 
        cost_xlims = cost_plot.get_xlim()
        cost_ylims = cost_plot.get_ylim()

        # Put text at midpoint of y
        cost_plot.axvline(self.sim_results['bau_draw'].apply(lambda x: x['discounted_costs'].sum()).mean()/1000, color='red')

        text_y2 = (cost_ylims[1] - cost_ylims[0]) / 2

        # offset by 10% of length of x-axis
        text_x2 = (
            self.sim_results['bau_draw'].apply(lambda x: x['discounted_costs'].sum()).mean()/1000 + (cost_xlims[1] - cost_xlims[0]) * 0.1
        )
        cost_plot.text(text_x2, text_y2, "Mean\nBAU\nCost")

        return fig, (benefit_plot, cost_plot)

    def plot_sim_trajectories(self, data_of_interest="benefits", save=None):

        fig, ax = plt.subplots()

        if data_of_interest == "benefits":
            col_of_interest = "opt_benefit"
            ylabel_interest = "Individuals"
        elif data_of_interest == "costs":
            col_of_interest = "opt_costs"
            ylabel_interest = "2019 USD"
        
        df_all = self.sim_results['opt_df'].apply(lambda x: x[col_of_interest].groupby(self.time_col).sum()).T

        # Now get mean trajectory

        df_all.plot(color='red', alpha=0.09, ax=ax, legend=False)
        df_all.mean(axis=1).plot(ax=ax, color="black")

        # plt.figtext(0, 0, "Bold line represents mean trajectory.")
        ax.set_title("Trajectories of all Simulations")
        
        ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}'))
        ax.set_ylabel(ylabel_interest)

        if save is not None:
            plt.savefig(save, dpi=160)

        return ax

    def plot_intervention_stacked(self, intervention_group=None, intervention_names = None, indicator_spec=3):
        
        fig, ax = plt.subplots()

        all_opt_df = (self._all_opt_df()
                      .groupby(['intervention', 'time', 'iteration'])
                      ['opt_vals']
                      .sum()
                      .to_frame()
                      .assign(opt_vals = lambda df: (df['opt_vals']>indicator_spec).astype(int))
                      )
        
        int_group = (
            all_opt_df[all_opt_df['opt_vals']>indicator_spec]
            .reset_index(level=self.intervention_col)
            [self.intervention_col]
            .str.extractall('|'.join([f"(?P<{j}>{i})" for i, j in zip(intervention_group, intervention_names)]))
         )             
        
        int_group.groupby(self.time_col).count().apply(lambda x: x/x.sum(), axis=1).plot.bar(stacked=True, ax=ax)
                   
        
        ax.legend(loc = 'lower left', bbox_to_anchor=(1.0, 0.5))
        ax.set_ylabel("% of Occurrences")
        ax.set_xlabel("Time")
        
        return ax

    