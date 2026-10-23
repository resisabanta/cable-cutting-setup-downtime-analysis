-- All summaries count only unplanned stops. Setup/inspection minutes are separate.
SELECT event_type, COUNT(*) AS event_count, SUM(duration_minutes) AS minutes
FROM synthetic_machine_events GROUP BY event_type ORDER BY event_type;

-- Pareto of recorded symptoms (not confirmed root causes).
WITH totals AS (
    SELECT cause, COUNT(*) AS stop_count, SUM(duration_minutes) AS downtime_minutes
    FROM synthetic_machine_events WHERE event_type='unplanned_stop' GROUP BY cause
)
SELECT *, ROUND(100.0*downtime_minutes/SUM(downtime_minutes) OVER (),2) AS share_percent,
    ROUND(100.0*SUM(downtime_minutes) OVER (ORDER BY downtime_minutes DESC,cause ROWS UNBOUNDED PRECEDING)
          /SUM(downtime_minutes) OVER (),2) AS cumulative_percent
FROM totals ORDER BY downtime_minutes DESC,cause;

SELECT configuration_id,machine_id,machine_section,COUNT(*) AS stop_count,
       SUM(duration_minutes) AS downtime_minutes,ROUND(AVG(duration_minutes),2) AS mean_stop_minutes
FROM synthetic_machine_events WHERE event_type='unplanned_stop'
GROUP BY configuration_id,machine_id,machine_section
ORDER BY configuration_id,downtime_minutes DESC;

-- Overnight events belong to the date when their shift starts.
SELECT shift_date,shift,COUNT(*) AS stop_count,SUM(duration_minutes) AS downtime_minutes
FROM synthetic_machine_events WHERE event_type='unplanned_stop'
GROUP BY shift_date,shift ORDER BY shift_date,shift;

-- Equipment descriptions via explicit keys; do not parse text for capabilities.
SELECT c.configuration_id,c.equipment_code,c.equipment_description,
       COUNT(e.event_id) AS stop_count,COALESCE(SUM(e.duration_minutes),0) AS downtime_minutes
FROM machine_configurations c LEFT JOIN synthetic_machine_events e
  ON (c.configuration_id,c.machine_id,c.machine_section)=(e.configuration_id,e.machine_id,e.machine_section)
 AND e.event_type='unplanned_stop'
WHERE c.machine_section='collection_machine'
GROUP BY c.configuration_id,c.equipment_code,c.equipment_description ORDER BY c.configuration_id;
