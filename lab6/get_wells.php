<?php
header('Content-Type: application/json');

$conn = new mysqli("localhost", "root", "DSCI560&team", "DS560Team6");

if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

$sql = "SELECT w.*, s.* 
        FROM wells w 
        LEFT JOIN stimulations s ON w.api = s.well_api";
$result = $conn->query($sql);

$rows = [];
while ($row = $result->fetch_assoc()) {
    $rows[] = $row;
}

echo json_encode($rows);
$conn->close();
?>
