# Data Preparation Script for Microservices Energy Efficiency Study

# This script performs:
# 1. Check missing values
# 2. Validate data type and ranges
# 3. Identify outliers
# 4. Create derived variables
# 5. Normality assessment with Shapiro-Wilk test

library(readr)
library(dplyr)
library(ggplot2)

data_path <- "data/run_table.csv"
output_path <- "data/prepared_data.csv"

raw_data <- read_csv(data_path, show_col_types = FALSE)

# =============================================================================
# 1. CHECK MISSING VALUES
# =============================================================================

missing_count <- sum(is.na(raw_data))
if(missing_count > 0) {
  cat("Found", missing_count, "missing values\n")
} else {
  cat("No missing values found\n")
}

# =============================================================================
# 2. DATA VALIDATION
# =============================================================================


processed_data <- raw_data %>%
  filter(`__done` == "DONE") %>%
  mutate(
    cpu_governor = as.factor(cpu_governor),
    load_type = as.factor(load_type),
    load_level = as.factor(load_level)
  )

cat("Removed", nrow(raw_data) - nrow(processed_data), "incomplete runs\n")
cat("CPU Governors:", paste(unique(processed_data$cpu_governor), collapse = ", "), "\n")
cat("Load Types:", paste(unique(processed_data$load_type), collapse = ", "), "\n")
cat("Load Levels:", paste(unique(processed_data$load_level), collapse = ", "), "\n")

# =============================================================================
# 3. OUTLIER DETECTION
# =============================================================================

detect_outliers <- function(data, variables) {
  outlier_summary <- data.frame(
    variable = character(),
    n_outliers = integer(),
    outlier_percentage = numeric(),
    stringsAsFactors = FALSE
  )
  
  for (var in variables) {
    if (var %in% colnames(data)) {
      var_data <- data[[var]]
      var_data <- var_data[!is.na(var_data)]
      
      if (length(var_data) > 0) {
        Q1 <- quantile(var_data, 0.25)
        Q3 <- quantile(var_data, 0.75)
        IQR <- Q3 - Q1
        
        lower_bound <- Q1 - 1.5 * IQR
        upper_bound <- Q3 + 1.5 * IQR
        
        outliers <- var_data[var_data < lower_bound | var_data > upper_bound]
        
        outlier_summary <- rbind(outlier_summary, data.frame(
          variable = var,
          n_outliers = length(outliers),
          outlier_percentage = round((length(outliers) / length(var_data)) * 100, 2),
          stringsAsFactors = FALSE
        ))
      }
    }
  }
  return(outlier_summary)
}

# Detect outliers in key variables
key_variables <- c("DRAM_ENERGY (J)", "PACKAGE_ENERGY (J)", "throughput", 
                   "latency_p50", "latency_p90", "latency_p95", "latency_p99", "run_time")

outlier_summary <- detect_outliers(processed_data, key_variables)
cat("Outlier detection summary:\n")
print(outlier_summary)

# =============================================================================
# 4. CREATE DERIVED VARIABLES
# =============================================================================

processed_data <- processed_data %>%
  mutate(
    # Energy metrics
    #application-level energy consumption
    total_application_energy = media_service_energy_joules + home_timeline_service_energy_joules + compose_post_service_energy_joules,
    #machine-level energy consumption
    total_machine_energy = `DRAM_ENERGY (J)` + `PACKAGE_ENERGY (J)`,

    # CPU metrics
    cpu_usage_mean = rowMeans(select(., starts_with("CPU_USAGE_")), na.rm = TRUE),
    cpu_usage_max = apply(select(., starts_with("CPU_USAGE_")), 1, max, na.rm = TRUE),
    cpu_freq_mean = rowMeans(select(., starts_with("CPU_FREQUENCY_")), na.rm = TRUE),
    cpu_freq_max = apply(select(., starts_with("CPU_FREQUENCY_")), 1, max, na.rm = TRUE),
    
    # Memory utilization
    memory_utilization = USED_MEMORY / TOTAL_MEMORY,
    
    # Experimental condition
    experimental_condition = paste(cpu_governor, load_type, load_level, sep = "_")
  )

# =============================================================================
# 5. NORMALITY ASSESSMENT
# =============================================================================

assess_normality <- function(data, variables) {
  normality_results <- data.frame(
    variable = character(),
    n_observations = integer(),
    shapiro_p_value = numeric(),
    is_normal = logical(),
    transformation_applied = character(),
    final_shapiro_p_value = numeric(),
    final_is_normal = logical(),
    recommended_test = character(),
    stringsAsFactors = FALSE
  )
  
  for (var in unique(variables)) {  
    if (var %in% colnames(data)) {
      var_data <- data[[var]]
      var_data <- var_data[!is.na(var_data)]
      n_obs <- length(var_data)
      
      if (n_obs >= 3 && n_obs <= 5000) {
        # Initial Shapiro-Wilk test
        shapiro_result <- shapiro.test(var_data)
        initial_p <- shapiro_result$p.value
        initial_normal <- initial_p > 0.05
        
        transformation_applied <- "none"
        final_p <- initial_p
        final_normal <- initial_normal
        
        # If not normal, try transformations in sequence
        if (!initial_normal) {
          transformations <- list(
            log = function(x) if (all(x > 0)) log(x) else NA,
            sqrt = function(x) if (all(x >= 0)) sqrt(x) else NA,
            # boxcox = function(x) if (all(x > 0)) car::powerTransform(x)$lambda else NA
            reciprocal = function(x) if (all(x != 0)) 1/x else NA
          )
          
          for (trans_name in names(transformations)) {
            if (!final_normal) { 
              trans_func <- transformations[[trans_name]]
              trans_data <- tryCatch(
                trans_func(var_data),
                error = function(e) NA
              )
              
              if (!any(is.na(trans_data))) {
                trans_shapiro <- shapiro.test(trans_data)
                if (trans_shapiro$p.value > 0.05) {
                  transformation_applied <- trans_name
                  final_p <- trans_shapiro$p.value
                  final_normal <- TRUE
                  break  
                }
              }
            }
          }
        }
        
        # Determine recommended test based on final normality
        recommended_test <- ifelse(final_normal, 
                                 "Parametric tests (ANOVA, Pearson correlation)",
                                 "Non-parametric tests (Kruskal-Wallis, Scheirer-Ray-Hare, Spearman correlation)")
        
        normality_results <- rbind(normality_results, data.frame(
          variable = var,
          n_observations = n_obs,
          shapiro_p_value = initial_p,  
          is_normal = initial_normal,
          transformation_applied = transformation_applied,
          final_shapiro_p_value = final_p, 
          final_is_normal = final_normal,
          recommended_test = recommended_test,
          stringsAsFactors = FALSE
        ))
      } else {
        # Handle cases with too few observations or too many
        cat("Skipping", var, "- invalid sample size:", n_obs, "\n")
      }
    }
  }
  
  return(normality_results)
}

cat("\n=== 5. NORMALITY ASSESSMENT ===\n")

# Assess normality for key variables
normality_vars <- c("total_application_energy", "total_machine_energy", 
                    "media_service_energy_joules", "home_timeline_service_energy_joules", 
                    "compose_post_service_energy_joules",
                    "throughput", "latency_p50", "latency_p90", 
                    "latency_p95", "latency_p99", "run_time", "cpu_usage_mean", 
                    "cpu_freq_mean", "memory_utilization")

normality_assessment <- assess_normality(processed_data, normality_vars)

cat("\nNormality Assessment Results:\n")
print(normality_assessment)

# Summary of normality results
normal_vars <- normality_assessment$variable[normality_assessment$final_is_normal]
non_normal_vars <- normality_assessment$variable[!normality_assessment$final_is_normal]


# =============================================================================
# 6. SAVE PREPARED DATA
# =============================================================================

# Select key variables for analysis
key_analysis_vars <- c(
  "__run_id", "cpu_governor", "load_type", "load_level", "experimental_condition",
  "total_application_energy", "total_machine_energy", "DRAM_ENERGY (J)", "PACKAGE_ENERGY (J)",
  "media_service_energy_joules", "home_timeline_service_energy_joules", 
  "compose_post_service_energy_joules",
  "throughput", "latency_p50", "latency_p90", "latency_p95", "latency_p99",
  "run_time", "cpu_usage_mean", "cpu_freq_mean",
  "memory_utilization", "USED_MEMORY", "TOTAL_MEMORY"
)

# Filter to key variables
analysis_data <- processed_data %>%
  select(all_of(key_analysis_vars))

# Save prepared data
write_csv(analysis_data, output_path)

# =============================================================================
# 7. SUMMARY
# =============================================================================

cat("\nFinal dataset information:\n")
cat("- Dimensions:", nrow(analysis_data), "rows x", ncol(analysis_data), "columns\n")
cat("- CPU governors:", paste(unique(analysis_data$cpu_governor), collapse = ", "), "\n")
cat("- Load types:", paste(unique(analysis_data$load_type), collapse = ", "), "\n")
cat("- Load levels:", paste(unique(analysis_data$load_level), collapse = ", "), "\n")

cat("\nRecommended Statistical Tests:\n")
anova_vars <- normality_assessment$variable[normality_assessment$final_is_normal]
nonparam_vars <- normality_assessment$variable[!normality_assessment$final_is_normal]

if(length(anova_vars) > 0) {
  cat("- Use parametric tests for:", paste(anova_vars, collapse = ", "), "\n")
}
if(length(nonparam_vars) > 0) {
  cat("- Use non-parametric tests for:", paste(nonparam_vars, collapse = ", "), "\n")
}

