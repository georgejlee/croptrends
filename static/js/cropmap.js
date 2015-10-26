var browserApp = angular.module('browserApp', ['uiGmapgoogle-maps', 'angularCharts'])
    .config(function (uiGmapGoogleMapApiProvider) {
        uiGmapGoogleMapApiProvider.configure({
            v: '3.22',
            key: '<YOUR GOOGLE MAPS KEY>'
        });
    });

browserApp
    .controller('cropBrowserCtrl', function ($scope, uiGmapGoogleMapApi, $timeout, $http) {
        $scope.doneLoading = false;
        $scope.isLoadingCrops = false;
        $scope.cropsError = false;
        $scope.noData = false;
        $scope.noGeo = false;
        $scope.location = "US TOTAL";
        $scope.selectedCrop = null;
        $scope.chartType = "bar";
        $scope.acreageChartConfig = {
            legend: {
                display: false,
                position: 'left',
                htmlEnabled: false
            },
            colors: ['rgb(70,132,238)'],
            xAxisMaxTicks: 2,
            yAxisTickFormat: '%',
            waitForHeightAndWidth: true
        };
        $scope.priceChartConfig = {
            legend: {
                display: false,
                position: 'left',
                htmlEnabled: false
            },
            colors: ['rgb(0,128,0)'],
            xAxisMaxTicks: 8,
            yAxisTickFormat: '$',
            waitForHeightAndWidth: true
        };

        $scope.topCropChartConfig = {
            legend: {
                display: false,
                position: 'left',
                htmlEnabled: false
            },
            title: '% of acres in region',
            yAxisTickFormat: '%',
            waitForHeightAndWidth: true
        };
        $scope.topCropChartData = {};
        $scope.chartData = {};
        $scope.priceChartData = {};

        var defaultCenter = {
            latitude: 37,
            longitude: -120
        };

        $scope.updateSelectedCrop = function (crop) {
            if (crop) {
                $scope.selectedCrop = crop;
            }
            var selectedCropData = $scope.cropDetailsChartData[$scope.selectedCrop];
            var title = "";
            var newAcreageChartData = {};
            if (selectedCropData) {
                title = "Acreage of " + $scope.selectedCrop;
                newAcreageChartData = selectedCropData.acreageChartData;
            }
            $scope.acreageChartData = newAcreageChartData;
            $scope.acreageChartConfig = {
                legend: {
                    display: false,
                    position: 'left',
                    htmlEnabled: false
                },
                title: title,
                xAxisMaxTicks: 5,
                yAxisTickFormat: '%',
                waitForHeightAndWidth: true
            };
            $scope.updatePricesForUtilPractice(0);

        };

        $scope.updatePricesForUtilPractice = function (priceTableIndex) {
            if (priceTableIndex != undefined) {
                $scope.priceTableIndex = priceTableIndex;
            }
            var selectedCropData = $scope.cropDetailsChartData[$scope.selectedCrop];
            var selectedPrice;
            var title = "No price data";
            var newPriceChartData = {};
            var newPriceTable = [];
            if (selectedCropData) {
                newPriceTable = selectedCropData.priceTable;
                newPriceChartData = selectedCropData.priceChartData[$scope.priceTableIndex];
                selectedPrice = newPriceTable[$scope.priceTableIndex];
                if (selectedPrice) {
                    var cropName = selectedPrice.fullCrop + " (" + selectedPrice.utilPractice + ")";
                    cropName = cropName.charAt(0).toUpperCase() + cropName.slice(1).toLowerCase();
                    title = "Price of " + cropName;
                }
            }
            $scope.priceTable = newPriceTable;
            $scope.priceChartConfig = {
                legend: {
                    display: false,
                    position: 'left',
                    htmlEnabled: false
                },
                title: title,
                xAxisMaxTicks: 8,
                yAxisTickFormat: '$',
                waitForHeightAndWidth: true
            };
            // Need to make sure config is updated before the data or else the new config won't take effect.
            $scope.priceChartData = newPriceChartData;
        };

        function loadTopCrops() {
            $http
                .get("/api/crops_in_circle", {
                    params: {
                        lat: $scope.circle.center.latitude,
                        lon: $scope.circle.center.longitude,
                        radius: $scope.circle.radius,
                        location: $scope.location
                    }
                })
                .success(function (data) {
                    $scope.doneLoading = true;
                    $scope.crops = data.crops;
                    $scope.isLoadingCrops = false;
                    $('#progress-modal').modal('hide')
                    $scope.cropsError = false;
                    $scope.noData = (data.topCropChartData.data.length == 0);
                    $scope.topCropChartData = data.topCropChartData;
                    $scope.topTrendsChartData = data.topTrendsChartData;
                    $scope.cropDetailsChartData = data.cropDetailsChartData;
                    var topTrendsCharts = [];
                    for (var i = 0; i < $scope.topTrendsChartData.length; i++) {
                        var chartData = $scope.topTrendsChartData[i];
                        var tickFormat;
                        var color;
                        if (chartData.series == "% Acres") {
                            tickFormat = "%";
                            color = 'rgb(70,132,238)';
                        } else {
                            tickFormat = "$";
                            color = 'rgb(0,128,0)';
                        }
                        var chartConfig = {
                            legend: {
                                display: false,
                                position: 'left',
                                htmlEnabled: false
                            },
                            colors: [color],
                            title: chartData.title,
                            xAxisMaxTicks: 3,
                            yAxisTickFormat: tickFormat,
                            waitForHeightAndWidth: true
                        };
                        topTrendsCharts.push({
                            chartType: "line",
                            chartConfig: chartConfig,
                            chartData: chartData
                        });
                    }
                    $scope.topTrendsCharts = topTrendsCharts;
                    var firstCrop = $scope.topCropChartData.data[0];
                    if (firstCrop) {
                        $scope.updateSelectedCrop(firstCrop.x);
                    } else {
                        $scope.updateSelectedCrop();
                    }
                    // A hack to force the graphs to update in case they haven't already.
                    $timeout(function () {
                        $scope.$apply(function () {
                        });
                    });
                })
                .error(function (data, status, headers, config) {
                    // show error message
                    $scope.crops = [];
                    $scope.isLoadingCrops = false;
                    $scope.noData = false;
                    $('#progress-modal').modal('hide');
                    $scope.cropsError = "Unable to load crop data, please try again."
                });
            $scope.isLoadingCrops = true;
            $('#progress-modal').modal('show');
            $scope.cropsError = false;
        }

        var recenter = function (map, newCenter) {
            $scope.noGeo = false;
            $scope.$apply(function () {
                $scope.marker.coords = {
                    latitude: newCenter.latitude,
                    longitude: newCenter.longitude
                };
                $scope.circle.center = {
                    latitude: newCenter.latitude,
                    longitude: newCenter.longitude
                };
            });

            if (map) {
                $timeout(function () {
                    map.panTo({
                        lat: newCenter.latitude,
                        lng: newCenter.longitude
                    });
                }, 200);
            } else {
                $scope.$apply(function () {
                    $scope.map.center = {
                        latitude: newCenter.latitude,
                        longitude: newCenter.longitude
                    };
                });
            }

            loadTopCrops($scope);
        };

        $scope.geolocate = function () {
            // Try HTML5 geolocation.
            if (navigator.geolocation) {
                $('#geo-modal').modal('show');
                navigator.geolocation.getCurrentPosition(function (position) {
                    recenter(null, {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    });
                    $('#geo-modal').modal('hide');
                }, function () {
                    $scope.$apply(function () {
                        $scope.noGeo = true;
                    });
                    $('#geo-modal').modal('hide');
                });
                // Dismiss the modal after 5 seconds in case the user does nothing.
                $timeout(function () {
                    $('#geo-modal').modal('hide');
                }, 5000);
            } else {
                $scope.$apply(function () {
                    $scope.noGeo = true;
                });
            }
        };


        uiGmapGoogleMapApi.then(function (maps) {
            $scope.map = {
                center: Object.create(defaultCenter),
                pan: true,
                zoom: 10,
                options: {
                    mapTypeId: maps.MapTypeId.HYBRID,
                    draggableCursor: "crosshair",
                    scrollwheel: false,
                    streetViewControl: false,
                    mapTypeControl: false
                },
                events: {
                    'click': function (map, eventName, arguments) {
                        var latLng = arguments[0].latLng;
                        var newCoords = {
                            latitude: latLng.lat(),
                            longitude: latLng.lng()
                        };
                        recenter(map, newCoords);
                    }
                }
            };

            $scope.marker = {
                idKey: "marker",
                coords: Object.create(defaultCenter),
                options: {
                    icon: {
                        path: 'M -5,0 5,0 z M 0,-5 0,5 z',
                        strokeColor: '#000',
                        strokeOpacity: 0.8,
                        strokeWeight: 0.5
                    },
                    clickable: false
                }
            };

            $scope.circle = {
                center: Object.create(defaultCenter),
                stroke: {
                    color: "#f00",
                    weight: 1,
                    opacity: 0.8
                },
                fill: {
                    color: "#f00",
                    opacity: 0.2
                },
                radius: 8046.72 // meters
            };

            loadTopCrops();
        });
    });
