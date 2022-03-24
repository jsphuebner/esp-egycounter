var chart;

function addToPlot(values)
{
	chart.config.data.labels.push(values['time']);

	for (var name in values)
	{
		var data = chart.config.data.datasets.find(function(element) { return element.label == name });
		
		chart.config.data.labels.splice(0, Math.max(chart.config.data.labels.length - 1000, 0));
		
		if (data)
		{
			data = data.data;
			data.push(values[name])
			data.splice(0, Math.max(data.length - 1000, 0));
		}
	}

	chart.update();
}

function loadSpot()
{
	var xmlhttp=new XMLHttpRequest();
	
	xmlhttp.onload = function() 
	{
		var values = JSON.parse(this.responseText);
		
		for (var item in values)
		{
			var span = document.getElementById(item);
			
			if (span)
				span.innerText = values[item];
		}
		
		addToPlot(values);
	}
		
	xmlhttp.open("GET", "index.php?spot=1", true);
	xmlhttp.send();
}

/** @brief generates chart at bottom of page */
function generateChart()
{
	chart = new Chart("canvas", {
		type: "line",
		options: {
			animation: {
				duration: 0
			},
			scales: {
				yAxes: [{
					type: "linear",
					display: true,
					position: "left",
					id: "left"
				}, {
					type: "linear",
					display: true,
					position: "right",
					id: "right",
					gridLines: { drawOnChartArea: false }
				}]
			}
		} });

	avgchart = new Chart("avgcanvas", {
		type: "line",
		options: {
			animation: {
				duration: 0
			},
			scales: {
				yAxes: [{
					type: "linear",
					display: true,
					position: "left",
					id: "left"
				}]
			}
		} });

	items = { names: [ "ptotal" ], axes: [ "left" ] };
	var colours = [ 'rgb(255, 99, 132)', 'rgb(54, 162, 235)', 'rgb(255, 159, 64)', 'rgb(153, 102, 255)', 'rgb(255, 205, 86)', 'rgb(75, 192, 192)' ];

	chart.config.data.datasets = new Array();

	for (var signalIdx = 0; signalIdx < items.names.length; signalIdx++)
	{
		var newDataset = {
		        label: items.names[signalIdx],
		        data: initdata[items.names[signalIdx]],
		        borderColor: colours[signalIdx % colours.length],
		        backgroundColor: colours[signalIdx % colours.length],
		        fill: false,
		        pointRadius: 0,
		        yAxisID: items.axes[signalIdx]
		    };
		chart.config.data.datasets.push(newDataset);
		chart.config.data.labels = initdata['time'];
	}

	var newDataset = {
	        label: "ptotal",
	        data: Object.values(avgdata),
	        borderColor: colours[0],
	        backgroundColor: colours[0],
	        fill: false,
	        pointRadius: 0,
	        yAxisID: "left"
	    };
	avgchart.config.data.datasets.push(newDataset);
	avgchart.config.data.labels = Object.keys(avgdata);
	
	chart.update();
	avgchart.update();
}

/** @brief excutes when page finished loading. Creates tables and chart */
function onLoad()
{
	setInterval(loadSpot, 1000);
	generateChart();
}

