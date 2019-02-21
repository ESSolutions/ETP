angular
  .module('essarch.controllers')
  .controller('OverwriteModalInstanceCtrl', function(
    $uibModalInstance,
    djangoAuth,
    data,
    SA,
    Profile,
    Notifications,
    $translate
  ) {
    var $ctrl = this;
    if (data.file) {
      $ctrl.file = data.file;
    }
    if (data.type) {
      $ctrl.type = data.type;
    }
    if (data.profile) {
      $ctrl.profile = data.profile;
    }
    $ctrl.overwriteProfile = function() {
      return Profile.update($ctrl.profile).$promise.then(function(resource) {
        Notifications.add($translate.instant('IMPORT.PROFILE_IMPORTED', resource), 'success', 5000, {isHtml: true});
        $ctrl.data = {
          status: 'overwritten',
        };
        $uibModalInstance.close($ctrl.data);
        return resource;
      });
    };
    $ctrl.overwriteSa = function() {
      $ctrl.profile.published = false;
      return SA.update($ctrl.profile).$promise.then(function(resource) {
        Notifications.add($translate.instant('IMPORT.SA_IMPORTED', resource), 'success', 5000, {isHtml: true});
        $ctrl.data = {
          status: 'overwritten',
        };
        $uibModalInstance.close($ctrl.data);
        return resource;
      });
    };
    $ctrl.overwrite = function() {
      $ctrl.data = {
        status: 'overwritten',
      };
      $uibModalInstance.close($ctrl.data);
    };
    $ctrl.cancel = function() {
      $uibModalInstance.dismiss('cancel');
    };
  });
