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

$last = $sqlDrv->scalarQuery("select max(time) from ebzdaily");
$last = new DateTime($last);
$start = $last->add(new DateInterval("PT1H"))->format('Y-m-d');
$end = (new DateTime())->format('Y-m-d');

$sql = "insert ignore into ebzdaily
select
	max(id) as id,
	counter_id,
	max(time) as time,
	max(etotal) as etotal,
	sum(if(ptotal>0, ptotal, 0))/(1000*3600) as etotalin,
	sum(if(ptotal<0, ptotal, 0))/(1000*3600) as etotalout,
	sum(pl1)/(1000*3600) as el1,
	sum(pl2)/(1000*3600) as el2,
	sum(pl3)/(1000*3600) as el3,
	sum(if(pbat>0, pbat, 0))/(1000*3600) as ebatin,
	sum(if(pbat<0, pbat, 0))/(1000*3600) as ebatout
from
	ebzdata
where
	time >= '$start' and time < '$end'
group by
	counter_id, SUBSTRING(time, 1, 10);";
	
$sqlDrv->query($sql);

$sql = "SELECT time,etotal,ptotal,pl1,pl2,pl3,pbat FROM ebzdata ORDER BY id DESC LIMIT 0, 1000";

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

$sql = "select sum(etotalout) from ebzdaily";
$unused = $sqlDrv->scalarQuery($sql);
$sql = "select sum(ptotal)/(1000*3600) from ebzdata where ptotal<0 and time > '$end'";
$unused += $sqlDrv->scalarQuery($sql);
$sql = "select sum(el3) from ebzdaily";
$ecar = $sqlDrv->scalarQuery($sql);
$sql = "select sum(pl3)/(1000*3600) from ebzdata where time > '$end'";
$ecar += $sqlDrv->scalarQuery($sql);
$sql = "select sum(ebatout) from ebzdaily";
$discharged = $sqlDrv->scalarQuery($sql);
$sql = "select sum(pbat)/(1000*3600) from ebzdata where pbat<0 and time > '$end'";
$discharged += $sqlDrv->scalarQuery($sql);
$sql = "select sum(ebatin) from ebzdaily";
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
<p><b>P-L1</b> [W]<span class='value' id='pl1'></span>
<p><b>P-L2</b> [W]<span class='value' id='pl2'></span>
<p><b>P-L3</b> [W]<span class='value' id='pl3'></span>
<p><b>P-Bat</b> [W] <span class='value' id="pbat"></span>
<p><b>E-Bat Chg</b> [kWh] <span class='value' id="charged"><?php echo $charged ?></span>
<p><b>E-Bat Dis</b> [kWh] <span class='value' id="discharged"><?php echo $discharged ?></span>
<p><b>PV ungenutzt</b> [kWh] <span class='value' id="pvunused"><?php echo $unused ?></span>
<p><b>E-Auto</b> [kWh] <span class='value' id="ecar"><?php echo $ecar ?></span>

<p><canvas id="canvas" width=100 height=40></canvas>
<p><canvas id="avgcanvas" width=100 height=40></canvas>

</body>
</html>
