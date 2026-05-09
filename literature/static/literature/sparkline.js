// ECharts sparkline init for tag/author landing pages — issue #27
// follow-up. Issue #80: extracted from the inline <script> in
// items/templates/items/show-entries.html so the CSP can drop
// 'unsafe-inline' from script-src.
//
// The ECharts library is loaded as a separate <script src="…"> tag
// that runs synchronously *before* this file, so the `echarts` global
// is available when this script executes. Data is read from the
// neighbouring <script id="lit-sparkline-data" type="application/json">
// emitted by Django's `{{ data|json_script }}` filter.
(function () {
    var node = document.getElementById('lit-sparkline-data');
    var mount = document.getElementById('lit-sparkline');
    if (!node || !mount || typeof echarts === 'undefined') return;
    var data = JSON.parse(node.textContent);
    if (data.length < 2) return;
    var years = data.map(function (p) { return p[0]; });
    var counts = data.map(function (p) { return p[1]; });
    var chart = echarts.init(mount);
    chart.setOption({
        grid: {top: 4, bottom: 4, left: 2, right: 2, containLabel: false},
        xAxis: {type: 'category', data: years, show: false, boundaryGap: false},
        yAxis: {type: 'value', show: false, min: 0},
        tooltip: {
            trigger: 'axis',
            formatter: function (p) {
                var n = p[0].data;
                return p[0].axisValue + ': ' + n + ' article' + (n === 1 ? '' : 's');
            }
        },
        series: [{
            type: 'line', data: counts,
            smooth: true, symbol: 'circle', symbolSize: 4,
            lineStyle: {width: 1.5},
            areaStyle: {opacity: 0.15}
        }]
    });
    window.addEventListener('resize', function () { chart.resize(); });
})();
