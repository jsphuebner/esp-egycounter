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
    primary key (id)
);

create index idx_ebz_time ON ebzdata(time);
*/
session_start();
//minimalistic access cotrol
if (!isset ($_SESSION['allow']))
{
	if (!isset($_GET['key']))
		die("No key provided");

	//Create with password_hash("yourpass", PASSWORD_DEFAULT)
	$expectedHash = '...hash...';

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
	//{ "id":"1EBZ0100200608","etotal":7307.09472656,"ptotal":4.51,"pphase":[35.24,-30.73,0.00]}
	$values = json_decode($_GET['data']);
	$pl1 = $values->pphase[0];
	$pl2 = $values->pphase[1];
	$pl3 = $values->pphase[2];
	
	$sql = "INSERT ebzdata (counter_id, etotal, ptotal, pl1, pl2, pl3) VALUES ('$values->id', $values->etotal, $values->ptotal, $pl1, $pl2, $pl3)";
	$sqlDrv->query($sql);
}
else if (isset($_GET['spot']))
{
	$sql = "SELECT * FROM ebzdata ORDER BY id DESC LIMIT 0, 1";

	$row = $sqlDrv->arrayQuery($sql)[0];
	
	echo json_encode($row);
}
else
{
	require('display.php');
}
