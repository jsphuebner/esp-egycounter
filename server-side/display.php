<!doctype html>
<html>
<head>
<title>EBZ Zaehler</title>
<style>
span.value {
	position: absolute;
	left: 12em;
}
</style>
<script src="chart.min.js" type="text/javascript"></script>
<script type="text/javascript">
var initdata = {};
var avgdata = {};
<?php

$_SESSION['allow'] = true;

$sql = "SELECT time,etotal,ptotal,pl1,pl2,pl3 FROM ebzdata ORDER BY id DESC LIMIT 0, 1000";

foreach ($sqlDrv->arrayQuery($sql) as $row)
{
	foreach ($row as $name => $value)
	{
		$result[$name][] = is_numeric($value) ? $value : "'$value'";
	}
}

foreach ($result as $name => $values)
{
	echo "initdata['$name'] = [ " . implode(",", array_reverse($values)) . "]" . PHP_EOL;
}

$sql = "SELECT MIN(time) time,AVG(ptotal) ptotal FROM ebzdata GROUP BY SUBSTRING(time, 1, 16) ORDER BY id DESC LIMIT 0, 1440";

echo "avgdata = {";
$comma = '';
foreach (array_reverse($sqlDrv->arrayQuery($sql)) as $row)
{
	echo $comma . '"' . $row['time'] . '":' . $row['ptotal'];
	$comma = ',';
}
echo "};";

$sql = "select sum(ptotal)/(1000*3600) from ebzdata where ptotal<0";
$unused = $sqlDrv->scalarQuery($sql);
?>
</script>
<script src="display.js" type="text/javascript"></script>
</head>
<body onload="onLoad()">
<p><b>Timestamp</b><span class='value' id='time'></span>
<p><b>E-Total</b> [kWh]<span class='value' id='etotal'></span>
<p><b>P-Total</b> [W]<span class='value' id='ptotal'></span>
<p><b>P-L1</b> [W]<span class='value' id='pl1'></span>
<p><b>P-L2</b> [W]<span class='value' id='pl2'></span>
<p><b>P-L3</b> [W]<span class='value' id='pl3'></span>
<p><b>PV ungenutzt</b> [kWh] <span class='value'><?php echo $unused ?></span>

<p><canvas id="canvas" width=100 height=40></canvas>
<p><canvas id="avgcanvas" width=100 height=40></canvas>
<?php
exit();
?>
<table border=1>
<tr><th>Timestamp</th><th>E-Total</th><th>P-Total</th><th>P-L1</th><th>P-L2</th><th>P-L3</th></tr>
<?php
$sql = "SELECT * FROM ebzdata WHERE time BETWEEN '$start' AND '$end'";
$data = $sqlDrv->arrayQuery($sql);

foreach ($data as $row)
{
	echo "<tr><td>" . $row['time'] . "</td><td>" . $row['etotal'] . "</td><td>" . $row['ptotal'] . "</td><td>" . $row['pl1'] . "</td><td>" . $row['pl2'] . "</td><td>" . $row['pl3'] . "</td></tr>";
}?>
</table>
