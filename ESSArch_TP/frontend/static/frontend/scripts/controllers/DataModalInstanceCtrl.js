angular.module('essarch.controllers').controller('DataModalInstanceCtrl', function (IP, $scope, $uibModalInstance, $http, appConfig, djangoAuth, $translate, Notifications, data) {
    var $ctrl = this;
    if(data.vm) {
        var vm = data.vm;
    }
    $ctrl.email = {
        subject: "",
        body: ""
    };
    $scope.prepareAlert = null;
    $ctrl.data = data;

    // Close prepare alert
    $scope.closePrepareAlert = function() {
        $scope.prepareAlert = null;
    }

    // Prepare IP for upload
    $ctrl.prepareForUpload = function(ip) {
        $ctrl.preparing = true;
        IP.prepareForUpload({ id: ip.id }).$promise.then(function(resource) {
            $ctrl.preparing = false;
            $uibModalInstance.close();
        }).catch(function(response) {
            $scope.prepareAlert = { msg: response.data.detail };
            $ctrl.preparing = false;
        })
    }

    // Set IP as uploaded
    $ctrl.setUploaded = function (ip) {
        $ctrl.settingUploaded = true;
        IP.setUploaded({
            id: ip.id
        }).$promise.then(function (response) {
            $ctrl.settingUploaded = false;
            $uibModalInstance.close();
        }).catch(function (response) {
            $ctrl.settingUploaded = false;
            if(response.status == 404) {
                Notifications.add('IP could not be found', 'error');
            } else if(response.data.detail) {
                Notifications.add(response.data.detail, 'error');
            }
        });
    }

    // Create SIP from IP
    $ctrl.createSip = function(ip) {
        $ctrl.creating = true;
        IP.create({
            id: ip.id,
            validators: vm.validatorModel,
            file_conversion: vm.fileConversionModel.file_conversion,
        }).$promise.then(function (response) {
            $ctrl.creating = false;
            $uibModalInstance.close();
        }).catch(function (response) {
            $ctrl.creating = false;
            if(response.status == 404) {
                Notifications.add('IP could not be found', 'error');
            } else if(response.data && response.detail){
                Notifications.add(response.data.detail, 'error');
            } else if(response.status !== 500) {
                Notifications.add('Unknown error!', 'error');
            }
        });
    }

    // Submit SIP
    $ctrl.submit = function (ip, email) {
        if(!email) {
            var sendData = {validators: vm.validatorModel}
        } else {
            var sendData = {validators: vm.validatorModel, subject: email.subject, body: email.body}
        }
        $ctrl.submitting = true;
        IP.submit(
            angular.extend({ id: ip.id }, sendData)
        ).$promise.then(function(response) {
            $ctrl.submitting = false;
            $uibModalInstance.close();
        }).catch(function(response) {
            $ctrl.submitting = false;
            if(response.status == 404) {
                Notifications.add('IP could not be found', 'error');
            } else {
                Notifications.add(response.data.detail, 'error');
            }
        });
    };

    // Remove IP
    $ctrl.remove = function (ipObject) {
        $ctrl.removing = true;
        IP.delete({
			id: ipObject.id
		}).$promise.then(function() {
            $ctrl.removing = false;
            $uibModalInstance.close($ctrl.data);
        }).catch(function(response) {
            if(response.status == 404) {
                Notifications.add('IP could not be found', 'error');
            } else {
                Notifications.add(response.data.detail, 'error');
            }
            $ctrl.removing = false;
        });
    };

    $ctrl.cancel = function () {
        $uibModalInstance.dismiss('cancel');
    };
});
