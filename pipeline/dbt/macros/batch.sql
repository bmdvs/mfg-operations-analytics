{# The export batch every mart row traces to. #}
{% macro batch_id() -%}
    (select export_batch_id from {{ ref('stg_erp__export_batch') }})
{%- endmacro %}
