<template>
  <div class="home">
    <PHeader></PHeader>
    <Pins :show-pin-details="showPinDetails"></Pins>
  </div>
</template>

<script>
import API from '../components/api';
import PHeader from '../components/PHeader.vue';
import Pins from '../components/Pins.vue';

export default {
  name: 'Home',
  components: {
    PHeader,
    Pins,
  },
  data() {
    return {
      showPinDetails: true,
    };
  },
  created() {
    API.SiteSettings.fetch().then(
      (siteSettings) => {
        this.showPinDetails = !siteSettings.hide_pin_details_on_home;
      },
    );
  },
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped lang="scss">
</style>
