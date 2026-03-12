# CEO Experience, Pay Sensitivity, and Performance: Formulas

## 1) Prior CEO Experience Indicator
For executive \(i\) in fiscal year \(t\):

\[
\text{PriorCEOExp}_{i,t} = \mathbb{1}[t > \min(\tau: CEO_{i,\tau}=1)]
\]

Interpretation:
- `0`: first CEO-year observed in ExecuComp history.
- `1`: executive has at least one prior CEO-year before year \(t\).

## 2) Forward 12-Month Buy-and-Hold Return (BHAR)
For firm-security link \(j\) and CEO-year ending at fiscal date \(T\):

\[
\text{BHAR}_{j,T+1:T+12} = \prod_{m=1}^{12}(1 + r_{j,T+m}) - 1
\]

where \(r_{j,T+m}\) is CRSP monthly return in month \(m\) after fiscal year-end.

## 3) Pay-Performance Sensitivity Model

\[
\ln(\text{TDC1}_{i,f,t}) =
\alpha + \beta_1 \text{BHAR}_{f,t+1:t+12}
+ \beta_2 \text{PriorCEOExp}_{i,t}
+ \beta_3 (\text{BHAR}_{f,t+1:t+12} \times \text{PriorCEOExp}_{i,t})
+ \gamma X_{i,f,t} + \delta_t + \varepsilon_{i,f,t}
\]

- Dependent variable: log total compensation (`tdc1`).
- \(X_{i,f,t}\): controls (`age`, pay scale proxy).
- Sample filter: firm-years with `BoardSize >= min_board_size` (default 3).
- \(\delta_t\): year fixed effects.
- Standard errors: clustered by firm (`gvkey`).

Interpretation of \(\beta_3\): difference in pay-performance slope for experienced vs inexperienced CEOs.

## 4) Performance Difference Model

\[
\text{BHAR}_{f,t+1:t+12} =
\alpha + \theta \text{PriorCEOExp}_{i,t} + \gamma X_{i,f,t} + \delta_t + u_{i,f,t}
\]

Interpretation of \(\theta\): average difference in subsequent stock performance between CEOs with prior CEO experience and first-time CEOs, conditional on controls.

## 5) Descriptive Statistics
By `PriorCEOExp` group, report:
- Number of observations
- Mean / median `tdc1`
- Mean / median forward 12-month BHAR
- Mean age

---

# S&P 500 Board Interconnectedness and Performance: Formulas

## 6) Interlock Intensity (Firm-Year)
For firm \(f\) in year \(t\), let each director be indexed by \(d\).

Number of S&P 500 boards served by director \(d\) in year \(t\):
\[
NBoards_{d,t} = \#\{f' \in S\&P500_t : d \text{ sits on board of } f'\}
\]

Outside seats contributed by director \(d\) on firm \(f\)'s board:
\[
OutsideSeats_{d,f,t} = \max(NBoards_{d,t} - 1, 0)
\]

Average outside seats for firm \(f\):
\[
AvgOutsideSeats_{f,t} = \frac{1}{|D_{f,t}|} \sum_{d \in D_{f,t}} OutsideSeats_{d,f,t}
\]

Share of interlocked directors:
\[
PctInterlocked_{f,t} = \frac{1}{|D_{f,t}|} \sum_{d \in D_{f,t}} \mathbb{1}[OutsideSeats_{d,f,t} > 0]
\]

where \(D_{f,t}\) is the set of directors on firm \(f\)'s board in year \(t\).

Total outside seats:
\[
TotalOutsideSeats_{f,t} = \sum_{d \in D_{f,t}} OutsideSeats_{d,f,t}
\]


## 7) Annual Buy-and-Hold Return
For firm-security \(j\) in calendar year \(t\):
\[
AnnualBHAR_{j,t} = \prod_{m \in t}(1 + r_{j,m}) - 1
\]

Forward return used in the regression:
\[
Fwd1YBHAR_{f,t} = AnnualBHAR_{f,t+1}
\]

## 8) Board Interlock-Performance Model
\[
Fwd1YBHAR_{f,t} = \alpha + \beta_1 AvgOutsideSeats_{f,t} + \beta_2 PctInterlocked_{f,t} + \beta_3 BoardSize_{f,t} + \delta_t + \varepsilon_{f,t}
\]

- Sample filter: firm-years with `BoardSize >= min_board_size` (default 3).
- \(\delta_t\): year fixed effects.
- Standard errors: clustered by firm (`gvkey`).

Interpretation of \(\beta_1\):
- \(\beta_1 > 0\) and statistically significant \(\Rightarrow\) interconnectedness helps.
- \(\beta_1 < 0\) and statistically significant \(\Rightarrow\) interconnectedness hurts.
- Not statistically significant \(\Rightarrow\) no detectable effect.
