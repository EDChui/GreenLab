# Data Exploration Script for RQ1.3
suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(purrr)
  library(stringr)
  library(coin)
  library(rcompanion)
  library(ARTool)
  library(emmeans)
  library(effsize)
})

# Configuration
input_path <- "data/prepared_data.csv"
fig_dir <- file.path("figures", "RQ1")
tab_dir <- file.path("tables", "RQ1")

# Create directories
dirs_to_create <- c(fig_dir, tab_dir)
for (dir in dirs_to_create) {
  if (!dir.exists(dir)) dir.create(dir, recursive = TRUE)
}

# Load and prepare data
data <- read_csv(input_path, show_col_types = FALSE)

# RQ1.3 descriptives: machine-level energy by workload and governor
rq1_3_df <- data %>%
  filter(!is.na(total_machine_energy)) %>%
  select(load_type, load_level, cpu_governor, total_machine_energy)

# Helper functions
calculate_descriptives <- function(data, group_vars, value_var) {
  data %>%
    group_by(across(all_of(group_vars))) %>%
    summarise(
      n = dplyr::n(),
      Mean = mean(.data[[value_var]], na.rm = TRUE),
      Std = sd(.data[[value_var]], na.rm = TRUE),
      Min = min(.data[[value_var]], na.rm = TRUE),
      `25%` = quantile(.data[[value_var]], 0.25, na.rm = TRUE, names = FALSE),
      Median = median(.data[[value_var]], na.rm = TRUE),
      `75%` = quantile(.data[[value_var]], 0.75, na.rm = TRUE, names = FALSE),
      Max = max(.data[[value_var]], na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(across(all_of(group_vars)))
}

create_separator <- function(char = "=", length = 60) {
  paste(rep(char, length), collapse = "")
}

# Calculate descriptives
rq1_3_desc <- calculate_descriptives(
  rq1_3_df, 
  c("load_type", "load_level", "cpu_governor"), 
  "total_machine_energy"
)

write_csv(rq1_3_desc, file.path(tab_dir, "rq1_3_machine_energy_by_workload_governor_descriptives.csv"))

# Governor-level summary table (across all workloads/load levels)
rq1_3_governor_summary <- rq1_3_df %>%
  group_by(cpu_governor) %>%
  summarise(
    n_observations = dplyr::n(),
    Mean = mean(total_machine_energy, na.rm = TRUE),
    Std = sd(total_machine_energy, na.rm = TRUE),
    Min = min(total_machine_energy, na.rm = TRUE),
    `25%` = quantile(total_machine_energy, 0.25, na.rm = TRUE, names = FALSE),
    Median = median(total_machine_energy, na.rm = TRUE),
    `75%` = quantile(total_machine_energy, 0.75, na.rm = TRUE, names = FALSE),
    Max = max(total_machine_energy, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(Mean)

write_csv(rq1_3_governor_summary, file.path(tab_dir, "rq1_3_governor_summary_across_all_workloads.csv"))

# Boxplot creation function
create_boxplot <- function(data, workload_type, fig_dir, governor_colors) {
  wt_data <- data %>% filter(load_type == workload_type)
  
  # Reorder load_level to high, medium, low
  wt_data$load_level <- factor(wt_data$load_level, levels = c("high", "medium", "low"))
  
  # Create proper x-axis positions for all combinations
  n_governors <- length(unique(wt_data$cpu_governor))
  governors <- sort(unique(wt_data$cpu_governor))
  
  wt_data <- wt_data %>%
    mutate(
      governor_num = match(cpu_governor, governors),
      load_level_num = match(load_level, c("high", "medium", "low")),
      x_pos = (load_level_num - 1) * n_governors + governor_num
    )
  
  # Create separator lines and labels
  separator_lines <- data.frame(
    x = c(n_governors + 0.5, 2 * n_governors + 0.5),
    xend = c(n_governors + 0.5, 2 * n_governors + 0.5),
    y = min(wt_data$total_machine_energy, na.rm = TRUE),
    yend = max(wt_data$total_machine_energy, na.rm = TRUE)
  )
  
  label_data <- data.frame(
    x = c(n_governors/2 + 0.5, n_governors + n_governors/2 + 0.5, 2*n_governors + n_governors/2 + 0.5),
    y = min(wt_data$total_machine_energy, na.rm = TRUE) * 0.95,
    label = c("High", "Medium", "Low")
  )
  
  p <- ggplot(wt_data, aes(x = x_pos, y = total_machine_energy, fill = cpu_governor, group = interaction(load_level, cpu_governor))) +
    stat_boxplot(geom = "errorbar", width = 0.3, alpha = 0.7, coef = 1.5) +
    geom_boxplot(outlier.size = 0.7, alpha = 0.8, show.legend = FALSE, coef = 1.5) +
    geom_segment(data = separator_lines, aes(x = x, xend = xend, y = y, yend = yend), 
                color = "dark gray", linewidth = 0.5, inherit.aes = FALSE) +
    geom_text(data = label_data, aes(x = x, y = y, label = label), 
              inherit.aes = FALSE, size = 7.5) +
    scale_fill_manual(values = governor_colors) +
    scale_x_continuous(breaks = 1:(3*n_governors), limits = c(0.5, 3*n_governors + 0.5)) +
    labs(x = "", y = "Total Machine Energy (J)") +
    theme_classic() +
    theme(
      plot.title = element_text(face = "bold", size = 20),
      plot.subtitle = element_text(size = 20),
      axis.title.y = element_text(size = 20),
      axis.text.y = element_text(size = 20),
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      panel.border = element_rect(color = "black", fill = NA),
      plot.margin = margin(15, 15, 15, 15)
    )
  
  filename <- paste0("rq1_3_machine_energy_boxplot_", tolower(gsub("[^A-Za-z0-9]", "_", workload_type)), ".png")
  ggsave(file.path(fig_dir, filename), p, width = 14, height = 8, dpi = 300)
}

# Create boxplots for each workload type
workload_types <- unique(rq1_3_df$load_type)
governor_colors <- c("#427AB2", "#F09148", "#FF9896", "#DBDB8D", "#C59D94", "#AFC7E8")
names(governor_colors) <- unique(rq1_3_df$cpu_governor)

for (wt in workload_types) {
  create_boxplot(rq1_3_df, wt, fig_dir, governor_colors)
}

# ART Test for Machine-Level Service Energy
data$cpu_governor <- as.factor(data$cpu_governor)
data$load_type <- as.factor(data$load_type)
data$load_level <- as.factor(data$load_level)

# Use total_machine_energy which represents the appropriate service energy for each workload
art_model_machine <- art(total_machine_energy ~ cpu_governor * load_type * load_level, data = data)
anova_result <- anova(art_model_machine)
print(anova_result)

# Post-hoc pairwise comparisons with Holm-Bonferroni correction
cat("\n", create_separator(), "\n")
cat("POST-HOC PAIRWISE COMPARISONS (Holm-Bonferroni correction)\n")
cat(create_separator(), "\n")

# Convert ART model to regular linear model for post-hoc analysis
lm_model_machine <- artlm(art_model_machine, "cpu_governor")

# Get emmeans for pairwise comparisons
emmeans_result <- emmeans(lm_model_machine, ~ cpu_governor)
pairwise_comparisons <- pairs(emmeans_result, adjust = "holm")

cat("\nPairwise comparisons for CPU Governor:\n")
print(pairwise_comparisons)

# Convert to data frame for saving
pairwise_df <- as.data.frame(pairwise_comparisons)
pairwise_df$contrast <- as.character(pairwise_df$contrast)

# Save pairwise comparisons
write_csv(pairwise_df, file.path(tab_dir, "rq1_3_posthoc_pairwise_comparisons_holm.csv"))

# Calculate Cliff's delta for pairwise comparisons
cat("\n", create_separator(), "\n")
cat("CLIFF'S DELTA EFFECT SIZES\n")
cat(create_separator(), "\n")

# Function to calculate Cliff's delta between two groups
calculate_cliffs_delta <- function(data, group1, group2, value_col) {
  group1_data <- data[data$cpu_governor == group1, value_col]
  group2_data <- data[data$cpu_governor == group2, value_col]
  
  # Remove NA values
  group1_data <- group1_data[!is.na(group1_data)]
  group2_data <- group2_data[!is.na(group2_data)]
  
  if (length(group1_data) == 0 || length(group2_data) == 0) {
    return(NA)
  }
  
  cliffs_result <- cliff.delta(group1_data, group2_data)
  return(cliffs_result$estimate)
}

# Get unique governors
governors <- unique(data$cpu_governor)
governors <- governors[!is.na(governors)]

# Calculate Cliff's delta for all pairwise comparisons
cliffs_results <- data.frame(
  group1 = character(),
  group2 = character(),
  cliffs_delta = numeric(),
  interpretation = character(),
  stringsAsFactors = FALSE
)

for (i in 1:(length(governors) - 1)) {
  for (j in (i + 1):length(governors)) {
    delta <- calculate_cliffs_delta(data, governors[i], governors[j], "total_machine_energy")
    
    # Interpret effect size
    if (abs(delta) < 0.11) {
      interpretation <- "negligible"
    } else if (abs(delta) < 0.28) {
      interpretation <- "small"
    } else if (abs(delta) < 0.43) {
      interpretation <- "medium"
    } else {
      interpretation <- "large"
    }
    
    cliffs_results <- rbind(cliffs_results, data.frame(
      group1 = governors[i],
      group2 = governors[j],
      cliffs_delta = delta,
      interpretation = interpretation,
      stringsAsFactors = FALSE
    ))
  }
}

# Print Cliff's delta results
cat("\nCliff's Delta Effect Sizes:\n")
print(cliffs_results)

# Save Cliff's delta results
write_csv(cliffs_results, file.path(tab_dir, "rq1_3_cliffs_delta_effect_sizes.csv"))

# Summary of significant differences
cat("\n", create_separator(), "\n")
cat("SUMMARY OF SIGNIFICANT DIFFERENCES\n")
cat(create_separator(), "\n")

# Extract significant pairwise comparisons (p < 0.05 after Holm correction)
significant_comparisons <- pairwise_df[pairwise_df$p.value < 0.05, ]

if (nrow(significant_comparisons) > 0) {
  cat("\nSignificant pairwise differences (p < 0.05 after Holm-Bonferroni correction):\n")
  for (i in 1:nrow(significant_comparisons)) {
    cat(sprintf("- %s: p = %.4f\n", 
                significant_comparisons$contrast[i], 
                significant_comparisons$p.value[i]))
  }
} else {
  cat("\nNo significant pairwise differences found after Holm-Bonferroni correction.\n")
}
