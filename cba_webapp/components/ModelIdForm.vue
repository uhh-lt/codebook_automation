<template>
  <b-form class="w-100" @submit="submitModelId">
    <b-form-group
      id="label-name"
      label="Name"
      label-for="input-name"
      description="Model-Id returned from Training"
      label-cols-md="4"
      label-cols-lg="2"
    >
      <b-input-group>
        <b-form-input
          id="input-model-id"
          v-model="model_id"
          placeholder="Enter Model-Id returned from Training"
          aria-describedby="input-model-id-feedback"
          required
          trim
          :state="modelIdInputState"
        />
        <b-input-group-append>
          <b-button variant="primary" @click="submitModelId">
            Get
          </b-button>
        </b-input-group-append>
        <b-form-invalid-feedback id="input-model-id-feedback">
          Not a valid Model-Id
        </b-form-invalid-feedback>
      </b-input-group>
    </b-form-group>
  </b-form>
</template>

<script>
export default {
  name: 'ModelIdForm',
  emits: ['models-id-submit'],
  data () {
    return {
      model_id: ''
    }
  },
  computed: {
    modelIdInputState () {
      return !!this.model_id.match(/[A-Za-z0-9]_mv_[A-Za-z0-9]+_dv_[A-Za-z0-9]+/)
    }
  },
  methods: {
    submitModelId (evt) {
      evt.preventDefault()
      this.$emit('model-id-submit', this.model_id)
    }
  }

}
</script>

<style scoped>

</style>
