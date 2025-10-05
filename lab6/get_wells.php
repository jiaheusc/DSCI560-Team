<?php
header('Content-Type: application/json; charset=utf-8');

// Turn on errors for debugging (set to 0 for production)
error_reporting(E_ALL);
ini_set('display_errors', 0);

// Database connection
$conn = new mysqli("localhost", "root", "DSCI560&team", "DS560Team6");

// Check connection
if ($conn->connect_error) {
    http_response_code(500);
    echo json_encode(["error" => "Database connection failed: " . $conn->connect_error]);
    exit;
}

// SQL query: join wells + stimulations (all columns)
$sql = "
    SELECT 
        w.id               AS well_id,
        w.filename,
        w.api,
        w.latitude_raw,
        w.longitude_raw,
        w.well_name,
        w.address,
        w.well_status,
        w.well_type,
        w.closest_city,
        w.latest_oil_production_bbl,
        w.latest_gas_production_mcf,
        w.latest_production_date,

        s.id                          AS stim_id,
        s.api,
        s.date_stimulated,
        s.stimulated_formation,
        s.top_ft,
        s.bottom_ft,
        s.stimulation_stages,
        s.volume,
        s.volume_units,
        s.type_treatment,
        s.acid_percentage,
        s.lbs_proppant,
        s.max_treatment_pressure_psi,
        s.max_treatment_rate_bbls_min,
        s.details
    FROM wells w
    LEFT JOIN stimulations s
      ON w.api = s.api  
    ORDER BY w.api ASC
";

// Execute query
$result = $conn->query($sql);

// Handle SQL errors
if (!$result) {
    http_response_code(500);
    echo json_encode(["error" => "SQL error: " . $conn->error]);
    $conn->close();
    exit;
}

// Collect rows
$rows = [];
while ($row = $result->fetch_assoc()) {
    $rows[] = $row;
}

// Output JSON
echo json_encode(
    [
        "status" => "ok",
        "count" => count($rows),
        "data" => $rows
    ],
    JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT
);

$conn->close();
?>

