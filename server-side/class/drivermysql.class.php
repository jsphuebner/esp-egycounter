<?php
define ("SQL_PORT", "port");
class MySqlDriver implements DBDriver
{
	private $connInfo;
	private $dbConn;
	private $lastStatement;

	function MySqlDriver($connInfo)
	{
		$this->connInfo = $connInfo;
	}

	function connect()
	{
		$this->dbConn = new mysqli ($this->connInfo[SQL_HOST], $this->connInfo[SQL_USER], $this->connInfo[SQL_PASS], $this->connInfo[SQL_DB], $this->connInfo[SQL_PORT]);
		if ($this->dbConn === false)
		{
			echo "<strong>An error occurred while connecting to database</strong><pre>";
			print_r ($this->dbConn->error);
			echo "</pre>";
			die ();
		}
		$this->lastStatement = $this->dbConn->select_db ($this->connInfo[SQL_DB]);
		$this->CheckStmt ('USE ' . $this->connInfo[SQL_DB]);
	}

	function delimField($name)
	{
		return "`$name`";
	}

	function escape($string)
	{
		return $this->dbConn->real_escape_string ($string);
	}

	function arrayQuery($sql, $col = null)
	{
		$this->query ($sql);
		return $this->getArrayResult ($col);
	}

	function scalarQuery($sql)
	{
		$this->query ($sql);
		return $this->getScalarResult ();
	}
	
	function mapQuery($sql, $key)
	{
		$this->query($sql);
		$map = array();
		
		while ($row = $this->getSingleRow ())
		{
			$currentKey = $row[$key];
			unset($row[$key]);
			if (count($row) > 1)
				$map[$currentKey] = $row;
			else
				$map[$currentKey] = array_values($row)[0];
		}
		
		return $map;
	}

	function query($sql, $nocheck = false)
	{
		$this->lastStatement = $this->dbConn->query ($sql);
		if (!$nocheck)
			$this->CheckStmt ($sql);
	}

	function callProcedure($name, &$params, $nocheck = false)
	{
		$sqlParams = array ();
		$sql = "CALL $name(";
		$outIdx = 0;
		foreach ($params as &$param)
		{
			if (!is_array ($param) || $param[1] == PARAM_IN)
			{
                $p = is_array ($param) ? $param[0] : $param;
				if (is_string ($p))
					$sqlParams[] = "'" . $this->dbConn->real_escape_string ($p) . "'";
				else if (NULL === $p)
					$sqlParams[] = "NULL";
				else if (is_numeric ($p))
					$sqlParams[] = "$p";
                else //bool
                    $sqlParams[] = (int)$p;
			}
			else
			{
				$sqlParams[] = "@out$outIdx";
				$outIdx++;
			}
		}
		$sql .= implode ($sqlParams, ",") . ')';
		$this->query ($sql, $nocheck);
		$outIdx = 0;
		foreach ($params as &$param)
		{
			if (is_array ($param) && $param[1] == PARAM_OUT)
			{
				$this->query ("SELECT @out$outIdx");
				$param[0] = $this->getScalarResult ();
				$outIdx++;
			}
		}
	}

	function getSingleRow()
	{
		return $this->lastStatement->fetch_assoc ();
	}

	function getScalarResult()
	{
		return $this->lastStatement->fetch_array (MYSQLI_NUM)[0];
	}

	function getArrayResult($col = null)
	{
		$values = array ();
		while ($row = $this->getSingleRow ())
		{
			if (null === $col)
				$values[] = $row;
			else
				$values[] = $row[$col];
		}
		while ($this->dbConn->more_results ())
			$this->dbConn->next_result ();
		$this->lastStatement->free ();
		return $values;
	}

	function useDatabase($db)
	{
		$this->lastStatement = $this->dbConn->select_db ($db);
		$this->CheckStmt ();
	}

	function getTableList($condition = "")
	{
		$this->query ("SHOW TABLES $condition");
		$tables = array ();
		while ($tables[] = $this->getScalarResult ())
		{
		}
		return $tables;
	}

	private function CheckStmt($sql = '')
	{
		if ($this->lastStatement === false)
		{
			echo "<strong>An error occurred while executing query</strong><pre>";
			print_r ($this->dbConn->error);
			echo PHP_EOL . "query was: $sql";
			echo "</pre>";
			die ();
		}
	}
}

?>
