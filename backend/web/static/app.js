<script>
    let ecsMetrics = window.ecsData.series[0].pointlist.map(([time, value]) => ({
        time: new Date(time * 1000).toLocaleTimeString(),
        value
    }));
    
    let labels = ecsMetrics.map(item => item.time);
    let data = ecsMetrics.map(item => item.value);

    onMount(() => {
        new Chart(document.getElementById("ecsChart"), {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Running Tasks",
                    data,
                    borderColor: "blue",
                    fill: false
                }]
            }
        });
    });
</script>
