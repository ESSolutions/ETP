/*
    ESSArch is an open source archiving and digital preservation system

    ESSArch Tools for Producer (ETP)
    Copyright (C) 2005-2017 ES Solutions AB

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.

    Contact information:
    Web - http://www.essolutions.se
    Email - essarch@essolutions.se
*/

angular.module('myApp').controller('BaseCtrl', function ($log, $uibModal, $timeout, $scope, $window, $location, $sce, $http, myService, appConfig, $state, $stateParams, $rootScope, listViewService, $interval, Resource, $translate, $cookies, $cookieStore, $filter, $anchorScroll, PermPermissionStore, $q){
    vm = this;
    $scope.updateIpsPerPage = function(items) {
        $cookies.put('etp-ips-per-page', items);
    };
    //Status tree view structure
    $scope.tree_data = [];
    $scope.angular = angular;
    $scope.checkPermission = function(permissionName) {
        return !angular.isUndefined(PermPermissionStore.getPermissionDefinition(permissionName));
    };
    $translate(['LABEL', 'RESPONSIBLE', 'DATE', 'STATE', 'STATUS']).then(function(translations) {
        $scope.responsible = translations.RESPONSIBLE;
        $scope.label = translations.LABEL;
        $scope.date = translations.DATE;
        $scope.state = translations.STATE;
        $scope.status = translations.STATUS;
        $scope.expanding_property = {
            field: "name",
            displayName: $scope.label,
        };
        $scope.col_defs = [
            {
                field: "user",
                displayName: $scope.responsible
            },
            {
                cellTemplate: "<div ng-include src=\"'static/frontend/views/task_pagination.html'\"></div>"
            },
            {
                field: "time_started",
                displayName: $scope.date

            },
            {
                field: "status",
                displayName: $scope.state,
                cellTemplate: "<div ng-if=\"row.branch[col.field] == 'SUCCESS'\" class=\"step-state-success\"><b>{{'SUCCESS' | translate}}</b></div><div ng-if=\"row.branch[col.field] == 'FAILURE'\" class=\"step-state-failure\"><b>{{'FAILURE' | translate}}</b></div><div ng-if=\"row.branch[col.field] != 'SUCCESS' && row.branch[col.field] !='FAILURE'\" class=\"step-state-in-progress\"><b>{{'INPROGRESS' | translate}}</b></div>"

            },
            {
                field: "progress",
                displayName: $scope.status,
                cellTemplate: "<uib-progressbar class=\"progress\" value=\"row.branch[col.field]\" type=\"success\"><b>{{row.branch[col.field]+\"%\"}}</b></uib-progressbar>"
            }
        ];
        if($scope.checkPermission("WorkflowEngine.can_undo") || $scope.checkPermission("WorkflowEngine.can_retry")) {
            $scope.col_defs.push(
            {
                cellTemplate: "<div ng-include src=\"'static/frontend/views/undo_redo.html'\"></div>"
            });
        }
    });
    $scope.myTreeControl = {};
    $scope.myTreeControl.scope = this;
    //Undo step/task
    $scope.myTreeControl.scope.taskStepUndo = function(branch) {
        $http({
            method: 'POST',
            url: branch.url+"undo/"
        }).then(function(response) {
            $timeout(function(){
                $scope.statusViewUpdate($scope.ip);
            }, 1000);
        }, function() {
            console.log("error");
        });
    };
    //Redo step/task
    $scope.myTreeControl.scope.taskStepRedo = function(branch){
        $http({
            method: 'POST',
            url: branch.url+"retry/"
        }).then(function(response) {
            $timeout(function(){
                $scope.statusViewUpdate($scope.ip);
            }, 1000);
        }, function() {
            console.log("error");
        });
    };
    $scope.currentStepTask = {id: ""}
    $scope.myTreeControl.scope.updatePageNumber = function(branch, page) {
        if(page > branch.page_number && branch.next){
            branch.page_number = parseInt(branch.next.page);
            listViewService.getChildrenForStep(branch, branch.page_number);
        } else if(page < branch.page_number && branch.prev && page > 0) {
            branch.page_number = parseInt(branch.prev.page);
            listViewService.getChildrenForStep(branch, branch.page_number);
        }
    };

    //Click on +/- on step
    $scope.stepClick = function(step) {
        listViewService.getChildrenForStep(step);
    };

    //Click funciton for steps and tasks
    $scope.stepTaskClick = function(branch) {
        $http({
            method: 'GET',
            url: branch.url
        }).then(function(response){
            var data = response.data;
            var started = moment(data.time_started);
            var done = moment(data.time_done);
            data.duration = done.diff(started);
            $scope.currentStepTask = data;
            if(branch.flow_type == "task"){
                $scope.taskInfoModal();
            } else {
                $scope.stepInfoModal();
            }
        }, function(response) {
            response.status;
        });
    };

    $scope.copyToClipboard = function() {
        $("#traceback_textarea").val($("#traceback_pre").html()).show();
        $("#traceback_pre").hide();
        $("#traceback_textarea").focus()[0].select();
        try {
            var successful = document.execCommand('copy');
            var msg = successful ? 'successful' : 'unsuccessful';
        } catch (err) {
            console.log('Oops, unable to copy');
        }
        $("#traceback_pre").html($("#traceback_textarea").val()).show();
        $("#traceback_textarea").hide();
    };
    //Redirect to admin page
    $scope.redirectAdmin = function () {
        $window.location.href="/admin/";
    }
    $scope.extendedEqual = function(specification_data, model) {
        for(var prop in model) {
            if((model[prop] != "" || specification_data[prop]) && model[prop] != specification_data[prop]){
                return false;
            }
        }
        return true;
    };
    //Update status view data
    $scope.statusViewUpdate = function(row){
        $scope.statusLoading = true;
        var expandedNodes = [];
        if($scope.tree_data != []) {
            expandedNodes = checkExpanded($scope.tree_data);
        }
        listViewService.getTreeData(row, expandedNodes).then(function(value) {
            $q.all(value).then(function(values) {
                console.log("Detta är vad vi får efter $q.all i ctrl!", values);
                if($scope.tree_data.length) {
                    $scope.tree_data = updateStepProperties($scope.tree_data, values);
                } else {
                    $scope.tree_data = value;
                }
            })
            $scope.statusLoading = false;
        }, function(response){
            if(response.status == 404) {
                $scope.statusShow = false;
                $timeout(function(){
                    $scope.getListViewData();
                    updateListViewConditional();
                }, 1000);
            }
        });
    };

    //Calculates difference in two sets of steps and tasks recursively
    //and updates the old set with the differances.
    function updateStepProperties(A, B) {
        if(A.length > B.length) {
            A.splice(0, B.length);
        }
        for (i = 0; i < B.length; i++) {
            if (A[i]) {
                if (B[i].children && B[i].children.length > 0 && B[i].children[0].val != -1) {
                    console.log("Rekursivt anrop: ", B[i].children);
                    var bTemp = B[i];
                    var aTemp = A[i];
                    $q.all(B[i].children).then(function(bchildren) {
                        console.log("B-CHILDREN AFTER SECOND $q.all!", bchildren)
                        aTemp.children = updateStepProperties(aTemp.children, bchildren);
                    })
                }
                A[i].id = compareAndReplace(A[i], B[i], "id");
                A[i].name = compareAndReplace(A[i], B[i], "name");
                A[i].user = compareAndReplace(A[i], B[i], "user");
                A[i].time_started = compareAndReplace(A[i], B[i], "time_started");
                A[i].status = compareAndReplace(A[i], B[i], "status");
                A[i].progress = compareAndReplace(A[i], B[i], "progress");
                A[i].undone = compareAndReplace(A[i], B[i], "undone");
                A[i].type = compareAndReplace(A[i], B[i], "type");
                
            } else {
                A.push(B[i]);
            }
        }
        return A;
    }

    //If A and B are not the same, make A = B
    function compareAndReplace(a, b, prop) {
        if (a[prop] && b[prop]) {

            if (a[prop] !== b[prop]) {
                console.log("---------------------------------------------------")
                console.log("compared and replaced", a[prop], " with ", b[prop]);
                console.log("---------------------------------------------------")
                a[prop] = b[prop];
            }
            return a[prop];
        } else {
            return b[prop]
        }
    }
    //checks expanded rows in tree structure
    function checkExpanded(nodes) {
        var ret = [];
        nodes.forEach(function(node) {
            if(node.expanded == true) {
                ret.push(node);
            }
            if(node.children && node.children.length > 0) {
                ret = ret.concat(checkExpanded(node.children));
            }
        });
        return ret;
    }

    $scope.tracebackModal = function (profiles) {
        $scope.profileToSave = profiles;
        var modalInstance = $uibModal.open({
            animation: true,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'static/frontend/views/task_traceback_modal.html',
            scope: $scope,
            size: 'lg',
            controller: 'ModalInstanceCtrl',
            controllerAs: '$ctrl'
        })
        modalInstance.result.then(function (data) {
        }, function () {
            $log.info('modal-component dismissed at: ' + new Date());
        });
    }
    //Creates and shows modal with task information
    $scope.taskInfoModal = function () {
        var modalInstance = $uibModal.open({
            animation: true,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'static/frontend/views/task_info_modal.html',
            scope: $scope,
            controller: 'ModalInstanceCtrl',
            controllerAs: '$ctrl'
        });
        modalInstance.result.then(function (data, $ctrl) {
        }, function () {
            $log.info('modal-component dismissed at: ' + new Date());
        });
    }
    //Creates and shows modal with step information
    $scope.stepInfoModal = function () {
        var modalInstance = $uibModal.open({
            animation: true,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'static/frontend/views/step_info_modal.html',
            scope: $scope,
            controller: 'ModalInstanceCtrl',
            controllerAs: '$ctrl'
        });
        modalInstance.result.then(function (data, $ctrl) {
        }, function () {
            $log.info('modal-component dismissed at: ' + new Date());
        });
    }
    //Create and show modal for remove ip
    $scope.removeIpModal = function (ipObject) {
        var modalInstance = $uibModal.open({
            animation: true,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'static/frontend/views/remove-ip-modal.html',
            controller: 'ModalInstanceCtrl',
            controllerAs: '$ctrl'
        })
        modalInstance.result.then(function (data) {
            $scope.removeIp(ipObject);
        }, function () {
            $log.info('modal-component dismissed at: ' + new Date());
        });
    }
});
