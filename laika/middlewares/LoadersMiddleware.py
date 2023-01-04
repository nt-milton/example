import integration.data_loaders as integration
import monitor.data_loaders as monitor
import program.data_loaders as program
import user.data_loaders as user
import vendor.data_loaders as vendor


class Loaders:
    def __init__(self, context):
        self.integration = integration.IntegrationLoaders(context)
        self.user = user.UserLoaders()
        self.vendor = vendor.VendorLoaders(context)
        self.monitor = monitor.MonitorLoaders(context)
        self.program = program.ProgramLoaders(context)


class LoaderMiddleware:
    @staticmethod
    def resolve(next, root, info, **args):
        if not hasattr(info.context, 'loaders'):
            info.context.loaders = Loaders(info.context)

        return next(root, info, **args)
