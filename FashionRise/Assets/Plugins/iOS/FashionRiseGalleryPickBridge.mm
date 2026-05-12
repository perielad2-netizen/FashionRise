#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <PhotosUI/PhotosUI.h>

extern "C" void UnitySendMessage(const char* className, const char* methodName, const char* option);

@class FRGalleryPickCoordinator;
static FRGalleryPickCoordinator* gGalleryPickCoordinator = nil;

@interface FRGalleryPickCoordinator : NSObject <PHPickerViewControllerDelegate, UIImagePickerControllerDelegate, UINavigationControllerDelegate>
@property (nonatomic, copy) NSString* importsDir;
@end

@implementation FRGalleryPickCoordinator

static void frgp_sendPath(NSString* absPathOrNil)
{
    const char* msg = absPathOrNil.length > 0 ? [absPathOrNil UTF8String] : "";
    dispatch_async(dispatch_get_main_queue(), ^{
        UnitySendMessage("FashionRiseAndroidBridge", "OnGalleryPick", msg);
    });
}

static NSString* frgp_writeJpeg(NSData* jpeg, NSString* dir)
{
    if (jpeg.length == 0 || dir.length == 0)
        return nil;
    NSFileManager* fm = [NSFileManager defaultManager];
    NSError* err = nil;
    BOOL ok = [fm createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:&err];
    if (!ok)
        return nil;
    long long ms = (long long)([[NSDate date] timeIntervalSince1970] * 1000.0);
    NSString* name = [NSString stringWithFormat:@"picked_%lld.jpg", ms];
    NSString* full = [dir stringByAppendingPathComponent:name];
    if (![jpeg writeToFile:full options:NSDataWritingAtomic error:&err])
        return nil;
    return full;
}

static UIViewController* frgp_topViewController(void)
{
    UIWindow* window = nil;
    if (@available(iOS 13.0, *))
    {
        for (UIScene* scene in UIApplication.sharedApplication.connectedScenes)
        {
            if (scene.activationState != UISceneActivationStateForegroundActive)
                continue;
            if (![scene isKindOfClass:[UIWindowScene class]])
                continue;
            UIWindowScene* ws = (UIWindowScene*)scene;
            for (UIWindow* w in ws.windows)
            {
                if (w.isKeyWindow)
                {
                    window = w;
                    break;
                }
            }
            if (window != nil)
                break;
        }
    }
    if (window == nil)
        window = UIApplication.sharedApplication.keyWindow;
    UIViewController* top = window.rootViewController;
    if (top == nil)
        return nil;
    while (top.presentedViewController != nil)
        top = top.presentedViewController;
    return top;
}

- (void)picker:(PHPickerViewController*)picker didFinishPicking:(NSArray<PHPickerResult*>*)results API_AVAILABLE(ios(14.0))
{
    NSString* dir = [self.importsDir copy];
    [picker dismissViewControllerAnimated:YES completion:nil];
    gGalleryPickCoordinator = nil;

    PHPickerResult* first = results.firstObject;
    if (first == nil)
    {
        frgp_sendPath(nil);
        return;
    }

    NSItemProvider* prov = first.itemProvider;
    if (![prov canLoadObjectOfClass:[UIImage class]])
    {
        frgp_sendPath(nil);
        return;
    }

    [prov loadObjectOfClass:[UIImage class]
          completionHandler:^(__kindof id<NSItemProviderReading> _Nullable object, NSError* _Nullable error) {
              UIImage* img = (UIImage*)object;
              if (img == nil || error != nil)
              {
                  frgp_sendPath(nil);
                  return;
              }
              NSData* jpeg = UIImageJPEGRepresentation(img, 0.92);
              NSString* path = frgp_writeJpeg(jpeg, dir);
              frgp_sendPath(path);
          }];
}

- (void)imagePickerController:(UIImagePickerController*)picker didFinishPickingMediaWithInfo:(NSDictionary*)info
{
    NSString* dir = [self.importsDir copy];
    UIImage* image = info[UIImagePickerControllerOriginalImage];
    [picker dismissViewControllerAnimated:YES
                               completion:^{
                                   gGalleryPickCoordinator = nil;
                                   if (image == nil)
                                   {
                                       frgp_sendPath(nil);
                                       return;
                                   }
                                   NSData* jpeg = UIImageJPEGRepresentation(image, 0.92);
                                   NSString* path = frgp_writeJpeg(jpeg, dir);
                                   frgp_sendPath(path);
                               }];
}

- (void)imagePickerControllerDidCancel:(UIImagePickerController*)picker
{
    [picker dismissViewControllerAnimated:YES
                                 completion:^{
                                     gGalleryPickCoordinator = nil;
                                     frgp_sendPath(nil);
                                 }];
}

@end

extern "C" void FrGalleryPick_Begin(const char* importsDirUtf8)
{
    NSString* dir = importsDirUtf8 ? [NSString stringWithUTF8String:importsDirUtf8] : @"";
    if (dir.length == 0)
    {
        frgp_sendPath(nil);
        return;
    }

    dispatch_async(dispatch_get_main_queue(), ^{
        UIViewController* top = frgp_topViewController();
        if (top == nil)
        {
            frgp_sendPath(nil);
            return;
        }

        gGalleryPickCoordinator = [[FRGalleryPickCoordinator alloc] init];
        gGalleryPickCoordinator.importsDir = dir;

        if (@available(iOS 14.0, *))
        {
            PHPickerConfiguration* cfg = [[PHPickerConfiguration alloc] init];
            cfg.filter = [PHPickerFilter imagesFilter];
            cfg.selectionLimit = 1;
            PHPickerViewController* picker = [[PHPickerViewController alloc] initWithConfiguration:cfg];
            picker.delegate = gGalleryPickCoordinator;
            [top presentViewController:picker animated:YES completion:nil];
        }
        else
        {
            UIImagePickerController* ipc = [[UIImagePickerController alloc] init];
            ipc.sourceType = UIImagePickerControllerSourceTypePhotoLibrary;
            ipc.delegate = gGalleryPickCoordinator;
            [top presentViewController:ipc animated:YES completion:nil];
        }
    });
}
