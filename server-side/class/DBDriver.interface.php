<?php
define ("SQL_HOST", "host");
define ("SQL_USER", "user");
define ("SQL_PASS", "pass");
define ("SQL_DB", "db");
define ("PARAM_IN", 0);
define ("PARAM_OUT", 1);
interface DBDriver
{

	function connect();

	function delimField($name);

	function arrayQuery($sql, $col = null);

	function scalarQuery($sql);
	
	function mapQuery($sql, $key);

	function query($sql, $nocheck = false);

	function callProcedure($name, &$params, $nocheck = false);

	function getSingleRow();

	function getScalarResult();

	function getArrayResult($col = null);

	function useDatabase($db);

	function getTableList($condition = "");
}

?>
