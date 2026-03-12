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
