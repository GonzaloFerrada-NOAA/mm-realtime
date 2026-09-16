msg()
{
    echo "$(date '+%F %T')    $1"
}

# =============================================================================
# =============================================================================

checkstatus() {
    local status=$?
    if (( status != 0 )); then
        echo "Command failed with exit status $status" >&2
        exit "$status"
    fi
}

# =============================================================================
# =============================================================================

isfile()
{
    local file="$1"
    if [[ ! -s "$file" ]]; then
        echo "ERROR: File does not exist or is empty: $file" >&2
        exit 1
    fi
}

# =============================================================================
# =============================================================================
get_group_leads()
{
    local fcst_length_hours="$1"
    local model_dt="$2"
    local ngroups="$3"
    local group="$4"

    local n_times base remainder n_group_times start_idx end_idx

    n_times=$(( fcst_length_hours / model_dt + 1 ))
    base=$(( n_times / ngroups ))
    remainder=$(( n_times % ngroups ))

    if (( group <= remainder )); then
        n_group_times=$(( base + 1 ))
    else
        n_group_times=$base
    fi

    start_idx=$(( (group - 1) * base + (group - 1 < remainder ? group - 1 : remainder) ))
    end_idx=$(( start_idx + n_group_times - 1 ))

    LEAD_HH_START=$(( start_idx * model_dt ))
    LEAD_HH_END=$(( end_idx * model_dt ))
}

# =============================================================================
# =============================================================================

