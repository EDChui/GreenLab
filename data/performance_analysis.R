# install.packages(c("tidyverse","car","emmeans","effectsize","rstatix","ARTool"))
# install.packages("effectsize")
library(tidyverse)
library(car)
library(emmeans)
library(effectsize)
library(rstatix)
library(ARTool)

# !!System specific!
setwd("C:/Users/Michiel/Documents/GreenLab/data-analysis")

prepared_data_path <- file.path("data", "prepared_data.csv")
prepared_data <- readr::read_csv(prepared_data_path)
# windows(width = 9, height = 7)

perf_cols <- grep("throughput|latency|p50|p90|p95|p99", names(prepared_data),
                  ignore.case = TRUE, value = TRUE)
print(perf_cols)
print(head(prepared_data[, perf_cols], 10))


basic_stats <- sapply(prepared_data[, perf_cols], function(x) c(
  n_nonmissing = sum(!is.na(x)),
  NAs         = sum(is.na(x)),
  zeros       = sum(x == 0, na.rm = TRUE),
  negatives   = sum(x < 0,  na.rm = TRUE),
  min         = min(x, na.rm = TRUE),
  q1          = as.numeric(quantile(x, 0.25, na.rm = TRUE)),
  median      = median(x, na.rm = TRUE),
  mean        = mean(x, na.rm = TRUE),
  q3          = as.numeric(quantile(x, 0.75, na.rm = TRUE)),
  max         = max(x, na.rm = TRUE)
))
print(round(t(basic_stats), 3))

par(cex = 1.1,
    cex.axis = 1.3,
    cex.lab  = 1.2,
    cex.main = 1.3)

gov_levels <- c("conservative","ondemand","performance","powersave","schedutil","userspace")
gov_cols <- c(
  conservative = "#FF9896",
  ondemand     = "#C59D94",
  performance  = "#F09148",
  powersave    = "#DBDB8D",
  schedutil    = "#427AB2",
  userspace    = "#AFC7E8"
)

load_levels_raw <- c("high","medium","low")
load_labels     <- c("High","Medium","Low")

apply_governor_levels <- function(df) {
  df$cpu_governor <- factor(df$cpu_governor, levels = gov_levels)
  df <- df[!is.na(df$cpu_governor), , drop = FALSE]
  droplevels(df)
}

make_load_factor <- function(x) {
  factor(x, levels = load_levels_raw, labels = load_labels)
}

plot_gov_box <- function(data, workload, metric_col, metric_label,
                         transform = identity, ylim_q = 0.995,
                         baseline_gov = "performance") {
  dx <- subset(data, load_type == workload)
  dx <- apply_governor_levels(dx)
  dx$load_hml <- make_load_factor(dx$load_level)

  ll <- levels(dx$load_hml)
  nG <- nlevels(dx$cpu_governor)
  if (length(dx$cpu_governor) == 0L || nG == 0L) {
    warning(sprintf("No rows to plot for workload '%s'.", workload))
    return(invisible())
  }

  cluster_gap    <- nG + 1
  base_pos       <- (seq_along(ll) - 1) * cluster_gap + (nG + 1) / 2
  within_offsets <- (1:nG) - (nG + 1) / 2
  at_pos         <- as.numeric(rep(base_pos, each = nG) +
                                 rep(within_offsets, times = length(ll)))

  col_vec <- rep(unname(gov_cols[levels(dx$cpu_governor)]), times = length(ll))

  dx$y_val <- transform(dx[[metric_col]])
  ylim_w   <- c(0, as.numeric(quantile(dx$y_val, ylim_q, na.rm = TRUE)))

  op <- par(mar = c(6,5,3,1)); on.exit(par(op), add = TRUE)

  boxplot(y_val ~ load_hml:cpu_governor, data = dx,
          at = at_pos, xaxt = "n", col = col_vec, outline = TRUE,
          ylim = ylim_w, ylab = metric_label, xlab = "", main = "")

  axis(1, at = base_pos, labels = ll)
  sep_at <- (head(base_pos, -1) + tail(base_pos, -1)) / 2
  abline(v = sep_at, lty = 3, col = "gray60")
}




#THROUGHPUT

plot_gov_box(prepared_data, workload = "compose_post",
             metric_col = "throughput",
             metric_label = "Throughput (requests/sec)",
             transform = function(x) x * 1000,
             ylim_q = 0.995, baseline_gov = "performance")

plot_gov_box(prepared_data, workload = "home_timeline",
             metric_col = "throughput",
             metric_label = "Throughput (requests/sec)",
             transform = function(x) x * 1000,
             ylim_q = 0.995, baseline_gov = "performance")

plot_gov_box(prepared_data, workload = "media",
             metric_col = "throughput",
             metric_label = "Throughput (requests/sec)",
             transform = function(x) x * 1000,
             ylim_q = 0.995, baseline_gov = "performance")


# LATENCY
plot_gov_box(prepared_data, workload = "compose_post",
             metric_col = "latency_p50",
             metric_label = "Latency p50 (ms)",
             transform = identity,
             ylim_q = 0.995, baseline_gov = "performance")

plot_gov_box(prepared_data, workload = "home_timeline",
             metric_col = "latency_p50",
             metric_label = "Latency p50 (ms)",
             transform = identity,
             ylim_q = 0.995, baseline_gov = "performance")

plot_gov_box(prepared_data, workload = "media",
             metric_col = "latency_p50",
             metric_label = "Latency p50 (ms)",
             transform = identity,
             ylim_q = 0.995, baseline_gov = "performance")



















#Normality check of residuals for a metric
do_normality <- function(metric_col,
                         transform = identity,
                         transform_name = "identity") {
  dx <- prepared_data
  dx <- apply_governor_levels(dx)
  dx$workload_f <- factor(dx$load_type)
  dx$load_hml   <- make_load_factor(dx$load_level)
  
  dx$y <- transform(dx[[metric_col]])
  dx <- dx[is.finite(dx$y) & !is.na(dx$y), , drop = FALSE]
  
  fit <- lm(y ~ cpu_governor * workload_f * load_hml, data = dx)
  res <- residuals(fit)
  
  qqnorm(res, main = sprintf("QQ plot of residuals: %s (%s)", metric_col, transform_name))
  qqline(res)
  
  if (length(res) >= 3 && length(res) <= 5000) {
    sw <- shapiro.test(res)
    print(sw)
  } else if (length(res) > 5000) {
    message("Sample is large (n = ", length(res), 
            "). Shapiro–Wilk is to sensitive")
    set.seed(1)
    sw <- shapiro.test(sample(res, 5000))
    print(sw)
  } else {
    stop("Not enough residuals for Shapiro–Wilk")
  }
  
  invisible(list(model = fit, residuals = res, shapiro = sw))
}


do_normality("throughput", function(x) x * 1000, "x * 1000")

# Latency p50 in ms (no transform)
# do_normality("latency_p50", identity, "identity")














check_assumptions <- function(metric_col, transform, name){
  dx <- prepared_data |> apply_governor_levels()
  dx$workload_f <- factor(dx$load_type)
  dx$load_hml   <- make_load_factor(dx$load_level)
  dx$y <- transform(dx[[metric_col]])
  dx <- dx[is.finite(dx$y) & !is.na(dx$y), ]
  
  fit <- lm(y ~ cpu_governor * workload_f * load_hml, data = dx)
  res <- rstandard(fit)
  qqnorm(res, main = sprintf("QQ: %s (%s)", metric_col, name)); qqline(res)
  
  set.seed(1)
  sh <- shapiro.test(if (length(res) > 5000) sample(res, 5000) else res)
  print(sh)
  
  lev <- car::leveneTest(y ~ cpu_governor * workload_f * load_hml, data = dx, center = median)
  print(lev)
  
  invisible(list(fit=fit, sh=sh, lev=lev))
}

# log scale
# check_assumptions("throughput",  function(x) log(x + 1e-6), "log")
check_assumptions("latency_p50", function(x) log(x + 1e-6), "log")
















#ART
rq2_art <- function(df, metric_col, transform = identity, metric_label = metric_col){
  dx <- df |> apply_governor_levels()
  dx$workload_f <- factor(dx$load_type)
  dx$load_hml   <- make_load_factor(dx$load_level)
  dx$y <- transform(dx[[metric_col]])
  dx <- dx[is.finite(dx$y) & !is.na(dx$y), , drop = FALSE]
  
  m <- ARTool::art(y ~ cpu_governor * workload_f * load_hml, data = dx)
  
  cat("\n=== ART ANOVA:", metric_label, "===\n")
  print(anova(m))
  
  emm <- emmeans::emmeans(
    ARTool::artlm(m, "cpu_governor:workload_f:load_hml"),
    ~ cpu_governor | workload_f * load_hml
  )
  print(pairs(emm, adjust = "holm"))
  
  
  cell_summ <- dx |>
    dplyr::group_by(workload_f, load_hml, cpu_governor) |>
    dplyr::summarise(median = median(y), IQR = IQR(y), .groups = "drop")
  cat("\n-- Cell medians & IQRs --\n"); print(cell_summ)
  invisible(list(model = m, emm = emm, summary = cell_summ))
}

rq2_art(prepared_data, "throughput",   function(x) x * 1000, "Throughput (req/s)")
rq2_art(prepared_data, "latency_p50",  identity,               "Latency p50 (ms)")












# Spearman 

library(dplyr)
library(purrr)
library(tibble)

energy_col <- "total_machine_energy"
perf_cols  <- c("throughput", "latency_p50")


if (!all(c("workload_f","load_hml") %in% names(prepared_data))) {
  prepared_data <- prepared_data %>%
    mutate(workload_f = factor(load_type),
           load_hml   = make_load_factor(load_level))
}

dat <- prepared_data %>%
  select(workload_f, load_hml, all_of(energy_col), all_of(perf_cols)) %>%
  filter(if_all(all_of(c(energy_col, perf_cols)), ~ is.finite(.)))

res <- dat %>%
  group_by(workload_f, load_hml) %>%
  group_modify(\(d, k) {
    map_dfr(perf_cols, \(m) {
      keep <- complete.cases(d[[energy_col]], d[[m]])
      n <- sum(keep)
      if (n < 3) return(tibble(metric = m, rho = NA_real_, statistic = NA_real_,
                               p.value = NA_real_, n = n))
      ct <- suppressWarnings(cor.test(d[[energy_col]][keep], d[[m]][keep],
                                      method = "spearman", exact = FALSE))
      tibble(metric = m,
             rho = unname(ct$estimate),
             statistic = unname(ct$statistic),
             p.value = ct$p.value,
             n = n)
    })
  }) %>%
  ungroup() %>%
  group_by(metric) %>%
  mutate(p_holm = p.adjust(p.value, method = "holm")) %>%
  ungroup() %>%
  arrange(metric, p_holm)

res











