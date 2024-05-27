<!doctype html>
<html>
<head>
<title>Energiemonitor</title>
<style>
span.value {
	position: absolute;
	left: 12em;
}
span.value2 {
	position: absolute;
	left: 17em;
}
span.value3 {
	position: absolute;
	left: 23em;
}
</style>
<script src="chart.min.js" type="text/javascript"></script>
<script type="text/javascript">
var initdata = {};
var avgdata = {};
<?php

$_SESSION['allow'] = true;

$last = $sqlDrv->scalarQuery("SELECT MAX(time) FROM ebzdaily");
$last = new DateTime($last);
$start = $last->add(new DateInterval("PT1H"))->format('Y-m-d');
$end = (new DateTime())->format('Y-m-d');

$sql = "INSERT IGNORE INTO ebzdaily
SELECT
	MAX(id) as id,
	counter_id,
	MAX(time) as time,
	MAX(etotal) as etotal,
	SUM(if(ptotal>0, ptotal, 0))/(1000*3600) as etotalin,
	SUM(if(ptotal<0, ptotal, 0))/(1000*3600) as etotalout,
	SUM(pl1)/(1000*3600) as el1,
	SUM(pl2)/(1000*3600) as el2,
	SUM(pl3)/(1000*3600) as el3,
	SUM(if(pbat>0, pbat, 0))/(1000*3600) as ebatin,
	SUM(if(pbat<0, pbat, 0))/(1000*3600) as ebatout
FROM
	ebzdata
WHERE
	time >= '$start' and time < '$end'
GROUP BY
	counter_id, SUBSTRING(time, 1, 10);";
	
$sqlDrv->query($sql);
$sql = "SELECT time,ptotal,pbat FROM ebzdata ORDER BY id DESC LIMIT 0, 1000";

foreach ($sqlDrv->arrayQuery($sql) as $row)
{
	foreach ($row as $name => $value)
	{
		$result[$name][] = is_numeric($value) ? $value : "'$value'";
	}
}

foreach ($result as $name => $values)
{
	echo "initdata['$name'] = [ " . implode(",", array_reverse($values)) . "];" . PHP_EOL;
}

$result = [];

if (isset($_GET['start']))
{
	$start = $_GET['start'];
	$stop = (new DateTime($start))->add(new DateInterval("PT24H"))->format('Y-m-d H:i:s');
}
else
{
	$start = (new DateTime("now", new DateTimeZone('Europe/Berlin')))->sub(new DateInterval("PT24H"))->format('Y-m-d H:i:s');
	$stop = (new DateTime("now", new DateTimeZone('Europe/Berlin')))->format('Y-m-d H:i:s');
}

$startId = $sqlDrv->scalarQuery("SELECT id FROM ebzdata WHERE time > '$start' LIMIT 1");
$endId = $sqlDrv->scalarQuery("SELECT id FROM ebzdata WHERE time < '$stop' ORDER BY id DESC LIMIT 1");
$sql = "SELECT MIN(time) time,AVG(ptotal) ptotal, AVG(pbat) pbat FROM ebzdata WHERE id BETWEEN $startId AND $endId GROUP BY SUBSTRING(time, 1, 16)";

//$time_pre = microtime(true);
foreach ($sqlDrv->arrayQuery($sql) as $row)
{
	foreach ($row as $name => $value)
	{
		$result[$name][] = is_numeric($value) ? $value : "'$value'";
	}
}

foreach ($result as $name => $values)
{
	echo "avgdata['$name'] = [ " . implode(",", $values) . "];" . PHP_EOL;
}

//$time_post = microtime(true);
//$exec_time = $time_post - $time_pre;
//echo "alert($exec_time);".PHP_EOL;

$sql = "select sum(etotalout) from ebzdaily";
$unused = $sqlDrv->scalarQuery($sql);
$sql = "select sum(ptotal)/(1000*3600) from ebzdata where ptotal<0 and time > '$end'";
$unused += $sqlDrv->scalarQuery($sql);
$sql = "select sum(el3) from ebzdaily";
$ecar = $sqlDrv->scalarQuery($sql);
//add energy from temporary 3-phase charging
$sql = "select sum(pl3)/(1000*3600)+174+14 from ebzdata where time > '$end'";
$ecar += $sqlDrv->scalarQuery($sql);
$sql = "select sum(ebatout) from ebzdaily";
$discharged = $sqlDrv->scalarQuery($sql);
$sql = "select sum(pbat)/(1000*3600) from ebzdata where pbat<0 and time > '$end'";
$discharged += $sqlDrv->scalarQuery($sql);
$sql = "select 3.1+sum(ebatin) from ebzdaily"; //correct for missing charge logs
$charged = $sqlDrv->scalarQuery($sql);
$sql = "select sum(pbat)/(1000*3600) from ebzdata where pbat>0 and time > '$end'";
$charged += $sqlDrv->scalarQuery($sql);
?>
</script>
<script src="display.js" type="text/javascript"></script>
</head>
<body onload="onLoad()">
<p><b>Timestamp</b><span class='value' id='time'></span>
<p><b>E-Total</b> [kWh]<span class='value' id='etotal'></span>
<p><b>P-Total</b> [W]<span class='value' id='ptotal'></span>
<p><b>P-L1/2/3</b> [W]<span class='value' id='pl1'></span><span class='value2' id='pl2'></span><span class='value3' id='pl3'></span>
<p><b>P-Bat</b> [W] <span class='value' id="pbat"></span>
<p><b>E-Bat Chg</b> [kWh] <span class='value' id="charged"><?php echo $charged ?></span>
<p><b>E-Bat Dis</b> [kWh] <span class='value' id="discharged"><?php echo $discharged ?></span>
<p><b>PV ungenutzt</b> [kWh] <span class='value' id="pvunused"><?php echo $unused ?></span>
<p><b>E-Auto</b> [kWh] <span class='value' id="ecar"><?php echo $ecar ?></span>

<p><canvas id="canvas" width=100 height=40></canvas>
<p><canvas id="avgcanvas" width=100 height=40></canvas>
<table border=1>
<thead><tr><th>Date</th><th>E-car</th><th>Month</th><th>E-Total</th><th>Day</th><th>Month</th></tr></thead>
<tbody>
<?php
function check_in_range($start_date, $end_date, $date_from_user)
{
  // Convert to timestamp
  $start_ts = strtotime($start_date);
  $end_ts = strtotime($end_date);
  $user_ts = strtotime($date_from_user);

  // Check that user date is between start & end
  return (($user_ts >= $start_ts) && ($user_ts <= $end_ts));
}

$sql = "select substring(time, 1, 10) date,etotal,el3 from ebzdaily";
$rows = $sqlDrv->arrayQuery($sql);

$lastEtotal = $rows[0]['etotal'];
$lastMonthTotal  = $lastEtotal;
$totalDelta = $rows[count($rows) - 1]['etotal'] - $lastEtotal;
$eCarSum = 0;
$eCarTotal = 0;

foreach ($rows as $row)
{
	$date = $row['date'];
	$etotal = $row['etotal'];
	if (($date < '2022-07-21' || $date > '2022-09-02') && $date != '2023-05-07')
		$ecar = round($row['el3'], 2);
	else
		$ecar = 3 * round($row['el3'], 2);
	$delta = round($etotal - $lastEtotal, 2);
	$eCarSum += $ecar;
	$eCarTotal += $ecar;
	$lastEtotal = $etotal;
	$deltaMonth = "";
	$eCarMonth = "";
	$dt = date_create($date);
	date_add($dt, date_interval_create_from_date_string("1 day"));
	$nextMonth = date_format($dt, "m");
	
	if (substr($date, 5, 2) != $nextMonth || $row == $rows[count($rows)-1])
	{
		$deltaMonth = round($etotal - $lastMonthTotal, 2);
		$lastMonthTotal = $etotal;
		$deltaMonth = "<td>$deltaMonth</td>";
		$eCarMonth = $eCarSum;
		$eCarSum = 0;
	}
	$htmlRows[] = "<tr><td><a href='?start=$date'>$date</a></td><td>$ecar</td><td>$eCarMonth</td><td>$etotal</td><td>$delta</td>$deltaMonth</tr>";
}

$daily = round($totalDelta / count($rows), 2);
$monthly = round($totalDelta / (count($rows) / 30), 2);
$eCarMonthly = round($eCarTotal / (count($rows) / 30), 2);
$htmlRows[] = "<tr><td><b>Total</b></td><td>$eCarTotal</td><td>$eCarMonthly</td><td>$totalDelta</td><td>$daily</td><td>$monthly</td></tr>";
echo implode(PHP_EOL, array_reverse($htmlRows));
?>
</tbody></table>
</body>
</html>
