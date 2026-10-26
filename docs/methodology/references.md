# References

## Pitch-control model

- **Spearman, W. (2018).** Beyond Expected Goals. *12th MIT Sloan Sports Analytics Conference.*
  The original conference link no longer works; a copy is kept in a
  [public collection of football analytics papers](https://github.com/eddwebster/football_analytics/blob/master/research/papers/%5B2018%5D%20Beyond%20Expected%20Goals%20-%20William%20Spearman.pdf).
  Source of the model and its parameters.

- **Dop, R. (2022).** Pitch control metrics to improve the predictions of moments leading to goals in
  football. MSc thesis, Information Studies (Data Science), University of Amsterdam.
  [PDF](https://staff.science.uva.nl/a.visser/education/masterProjects/Thesis_Ramon_Dop_MsDS.pdf)
  Section 2 states the model's assumptions independently of the reference code: a 0.7 s reaction time,
  a constant player speed of 5 m/s and a constant ball speed of 15 m/s.

- **Shaw, L.** LaurieOnTracking (Friends of Tracking).
  [github.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking](https://github.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking)
  Reference implementation used for validation.

## Velocities

- **Savitzky, A. & Golay, M. J. E. (1964).** Smoothing and differentiation of data by simplified least
  squares procedures. *Analytical Chemistry*, 36(8), 1627–1639.
  [doi:10.1021/ac60214a047](https://doi.org/10.1021/ac60214a047)
  The smoothing filter.

- **Haugen, T. A., Breitschädel, F. & Seiler, S. (2019).** Sprint mechanical variables in elite athletes:
  Are force-velocity profiles sport specific or individual? *PLoS ONE*, 14(7), e0215551.
  [doi:10.1371/journal.pone.0215551](https://doi.org/10.1371/journal.pone.0215551)
  Across elite male athletes, including sprinters and footballers, the theoretical maximum speed (v0) ranges
  from 7.5 to 11 m/s and the theoretical maximum horizontal force (F0) from 7 to 10 N/kg. Force per kilogram
  is acceleration, so no player accelerates faster than about 10 m/s². This supports the 12 m/s speed cap
  and the 10 m/s² acceleration limit.

- **Silva, H., Nakamura, F. Y., Racil, G., Gómez-Diaz, A., Menezes, P., Chamari, K. & Marcelino, R. (2025).**
  Peak match sprinting speed during soccer matches: analysing the pre- and post-peak speed dynamics.
  *Biology of Sport*, 42(1), 193–200.
  [doi:10.5114/biolsport.2024.136089](https://doi.org/10.5114/biolsport.2024.136089)
  Average peak match speeds by position of 29–32 km/h (8–9 m/s), well below the 12 m/s cap.

## Data

- **Metrica Sports sample data.** [github.com/metrica-sports/sample-data](https://github.com/metrica-sports/sample-data)
