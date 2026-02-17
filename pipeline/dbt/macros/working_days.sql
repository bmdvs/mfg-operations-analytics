{# Position of a timestamp on the working-day clock; needs int_working_days joined as cal_alias on the date of the timestamp. #}
{% macro wd(ts, cal_alias) -%}
    ({{ cal_alias }}.wd_index + {{ cal_alias }}.is_working_day::int * epoch({{ ts }} - cast(cast({{ ts }} as date) as timestamp)) / 86400.0)
{%- endmacro %}

{# Unbroken intervals within each partition: overlapping transactions merge into one interval. #}
{% macro interval_islands(relation, keys, start_col, end_col, where='true') -%}
    select {{ keys | join(', ') }}, island_id, min({{ start_col }}) as island_start, max({{ end_col }}) as island_end
    from (
        select *, sum(new_island) over (partition by {{ keys | join(', ') }} order by {{ start_col }}, {{ end_col }} rows unbounded preceding) as island_id
        from (
            select *,
                case when {{ start_col }} <= max({{ end_col }}) over (partition by {{ keys | join(', ') }} order by {{ start_col }}, {{ end_col }}
                                                                    rows between unbounded preceding and 1 preceding) then 0 else 1 end as new_island
            from {{ relation }}
            where {{ where }}
        )
    )
    group by {{ keys | join(', ') }}, island_id
{%- endmacro %}
