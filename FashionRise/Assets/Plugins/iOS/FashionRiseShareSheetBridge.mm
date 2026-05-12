#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

extern "C" void FrShareSheet_Show(const char* text, const char* subject)
{
    @autoreleasepool
    {
        NSString* shareText = text ? [NSString stringWithUTF8String:text] : @"";
        NSString* shareSubject = subject ? [NSString stringWithUTF8String:subject] : @"";
        NSMutableArray* items = [NSMutableArray array];
        if (shareText.length > 0) [items addObject:shareText];
        if (shareSubject.length > 0) [items addObject:shareSubject];
        if (items.count == 0) return;

        dispatch_async(dispatch_get_main_queue(), ^{
            UIViewController* root = UIApplication.sharedApplication.keyWindow.rootViewController;
            if (!root) return;
            UIViewController* top = root;
            while (top.presentedViewController != nil) top = top.presentedViewController;

            UIActivityViewController* vc = [[UIActivityViewController alloc] initWithActivityItems:items applicationActivities:nil];
            UIPopoverPresentationController* pop = vc.popoverPresentationController;
            if (pop)
            {
                pop.sourceView = top.view;
                pop.sourceRect = CGRectMake(CGRectGetMidX(top.view.bounds), CGRectGetMidY(top.view.bounds), 1, 1);
                pop.permittedArrowDirections = 0;
            }
            [top presentViewController:vc animated:YES completion:nil];
        });
    }
}
