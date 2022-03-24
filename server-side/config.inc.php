<?php
/**
 * @file
 * @brief This file contains configuration variables
 * @author Ingenieurbuero Johannes Huebner <dev@johanneshuebner.com>, Alte Str. 12, 34266 Niestetal
*/

if (!isset ($_config_included))
{
	$_config_included = true;
	
	require ("class/DBDriver.interface.php");
	require ("class/drivermysql.class.php");
	
	date_default_timezone_set ("UTC");

	$sqlDrv = new MySqlDriver(array(SQL_HOST => 'localhost', SQL_PORT => 3306, SQL_USER => 'yourname', SQL_PASS => 'yourpass', SQL_DB=> 'yourdb'));
}
?>
