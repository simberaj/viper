
import viper

ui = viper.UI(
  viper.TextInput('value', label='Input text', value='DEFAULT', updateMode='onchange'),
  viper.TextOutput('commentary')
)

class MyServer(viper.Server):
  def __init__(self):
    super().__init__(
      {'commentary' : (self.commentOnValue, 'value')}
    )
    self.ev = 0

    
  def commentOnValue(self, value):
    print(value, self.ev)
    self.ev += 1
    return 'Value was {} on evaluation run {}.'.format(value, self.ev)

    
app = viper.Application(ui, MyServer())
app.run()