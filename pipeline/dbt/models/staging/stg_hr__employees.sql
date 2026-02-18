select
    employee_id,
    role,
    home_work_center,
    shift,
    work_centers_qualified,
    cast(hire_date as date) as hire_date,
    cast(termination_date as date) as termination_date
from {{ source('hr', 'hr__employees') }}
