<?php
/*
create table ebzdata (
    id int not null AUTO_INCREMENT,
    counter_id varchar(20) not null,
    time datetime DEFAULT NOW(),
    etotal decimal(14, 8),
    ptotal decimal(10,2),
    pl1 decimal(10,2),
    pl2 decimal(10,2),
    pl3 decimal(10,2),
    pbat decimal(10,2),
    primary key (id)
);

create index idx_ebz_time ON ebzdata(time);

create table ebzdaily (
	id int not null,
    counter_id varchar(20) not null,
    time datetime,
    etotal float,
    etotalin float,
    etotalout float,
    el1 float,
    el2 float,
    el3 float,
    ebatin float,
    ebatout float,
    primary key (id)
);
*/
session_start();

if (!isset ($_SESSION['allow']))
{
	if (!isset($_GET['key']))
		die("No key provided");

	//Create $expectedHash with password_hash("yourpass", PASSWORD_DEFAULT) and put it in config.inc.php
	if (!password_verify ($_GET['key'] , $expectedHash))
		die (-1);
}

require ('config.inc.php');

$sqlDrv->connect();

if (isset($_GET['start']))
	$start = $_GET['start'];
else
	$start = (new DateTime())->sub(new DateInterval("P1D"))->format('Y-m-d h:i:s');

if (isset($_GET['end']))
	$end = $_GET['end'];
else
	$end = (new DateTime())->add(new DateInterval("PT1H"))->format('Y-m-d h:i:s');


if (isset($_GET['data']))
{
	//{ "id":"1EBZ0100200608","etotal":7307.09472656,"ptotal":4.51,"pbat": 300.0,"pphase":[35.24,-30.73,0.00]}
	$values = json_decode($_GET['data']);
	$pl1 = $values->pphase[0];
	$pl2 = $values->pphase[1];
	$pl3 = $values->pphase[2];
	
	$sql = "INSERT ebzdata (counter_id, etotal, ptotal, pl1, pl2, pl3, pbat) VALUES ('$values->id', $values->etotal, $values->ptotal, $pl1, $pl2, $pl3, $values->pbat)";
	$sqlDrv->query($sql);
}
else if (isset($_GET['spot']))
{
	$lastDelta = 0;
	$sql = "SELECT * FROM ebzdata ORDER BY id DESC LIMIT 0, 1";

	$row = $sqlDrv->arrayQuery($sql)[0];
	
	$sql = "SELECT ptotal FROM ebzdata ORDER BY id DESC LIMIT 0, 3";

	$rows = $sqlDrv->arrayQuery($sql, 'ptotal');
		
	if (isset($_SESSION['lastdelta']))
		$lastDelta = $_SESSION['lastdelta'];
		
	$delta[0] = $rows[0] - $rows[1];
	$delta[1] = $rows[1] - $rows[2];
	$delta[2] = $rows[0] - $rows[2];
	
	$absDeltas = array_map(fn($value): float => abs($value), $delta);
	$maxAbsDelta = max($absDeltas);
	$maxKey = array_search($maxAbsDelta, $absDeltas);
	$delta = $delta[$maxKey];
	
	if (abs($delta) > 8)
		$_SESSION['lastdelta'] = $delta;
	else
		$delta = $lastDelta;
		
	$row['delta'] = $delta;
	
	echo json_encode($row);
}
else if (isset($_GET['delta']))
{
	$sql = "SELECT ptotal FROM ebzdata ORDER BY id DESC LIMIT 0, 3";

	$rows = $sqlDrv->arrayQuery($sql, 'ptotal');
		
	if (isset($_SESSION['lastdelta']))
		$delta[0] = $_SESSION['lastdelta'];
		
	$delta[1] = $rows[1] - $rows[0];
	$delta[2] = $rows[2] - $rows[1];
	$delta[3] = $rows[2] - $rows[0];
	
	$absDeltas = array_map(fn($value): float => abs($value), $delta);
	$maxAbsDelta = max($absDeltas);
	$maxKey = array_search($maxAbsDelta, $absDeltas);
	$delta = $delta[$maxKey];
	
	if (abs($delta) > 8)
		$_SESSION['lastdelta'] = $delta;
	
	echo $delta;
}
else
{
	require('display.php');
}
