angular.module('myApp').controller('HeadCtrl', function($scope, $rootScope, $timeout, $translate, $state) {
    var vm = this;
    var appName = " | ESSArch Tools for Producer";
    vm.pageTitle = "ESSArch Tools for Producer";
    vm.responsiveTag = "";
    $rootScope.$on('$stateChangeSuccess', function (event, toState, toParams, fromState, fromParams) {
        vm.pageTitle = $translate.instant(toState.name.split(".").pop().toUpperCase())+appName;
        $scope.getResponsiveTag();
    });
    $rootScope.$on('$translateChangeSuccess', function () {
        vm.pageTitle = $translate.instant($state.current.name.split(".").pop().toUpperCase())+appName;
    });
    $scope.getResponsiveTag = function() {
        if($state.is("login")) {
            vm.responsiveTag = "width=device-width, initial-scale=1";
        } else {
            vm.responsiveTag = "width=680";
        }
    }
});
